from chatto_transform.transforms.transform_base import Transform

from chatto_transform.schema import schema_base as sb
from chatto_transform.schema.mimic.mimic_schema import labevents_schema, patients_schema

from chatto_transform.lib.mimic.session import load_table

import pandas as pd
import numpy as np

"""
select bucket, count(*) from (
  select width_bucket(valuenum, 0, 280, 280) as bucket
    from mimic2v26.labevents le,
         mimic2v26.d_patients dp
   where itemid in (50177)
     and le.subject_id = dp.subject_id
     and months_between(le.charttime, dp.dob)/12 > 15
  ) group by bucket order by bucket;
"""

class BUNTransform(Transform):
    def input_schema(self):
        return sb.MultiSchema({
            'labevents': labevents_schema,
            'patients': patients_schema
        })

    def _load(self):
        """Load the two tables (labevents and d_patients) separately.
        Since labevents is a very large table we select a subset of it before loading."""
        bun_labevents = load_table(labevents_schema, "itemid=51006") #"itemid=50177")
        patients = load_table(patients_schema)

        return {'labevents': bun_labevents, 'patients': patients}

    def _transform(self, tables):
        """Join the two tables on subject_id and convert their age to years,
        cutting off at <15 and >100"""
        labevents = tables['labevents']
        patients = tables['patients']

        labevents_schema.add_prefix(labevents)
        patients_schema.add_prefix(patients)

        df = pd.merge(labevents, patients, how='left',
            left_on='labevents.subject_id', right_on='patients.subject_id')

        age = df['labevents.charttime'] - df['patients.dob']
        age = age / np.timedelta64(1, 'Y') #convert to years
        age = np.floor(age) #round to nearest year
        df['age_at_labevent'] = age
        df = df[age >= 15]

        df['labevents.valuenum'] = np.floor(df['labevents.valuenum'])
        df = df[(df['labevents.valuenum'] >= 0) & (df['labevents.valuenum'] <= 280)]

        df['bun'] = df['labevents.valuenum']

        return df

class BUNHistTransform(Transform):
    def input_schema(self):
        return sb.PartialSchema('bun', [
            sb.num('bun')
        ])

    def _transform(self, bun_df):
        bun_counts = bun_df['bun'].value_counts().sort_index()

        return pd.DataFrame(bun_counts, columns=['count'])





