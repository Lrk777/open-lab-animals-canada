-- SQL and Python implementations of the Transparency Index must agree to 0.1 points.
select d.jurisdiction, d.index_0_100 as dbt_value, p.index_0_100 as python_value
from {{ ref('fct_transparency_index') }} d
join {{ source('raw', 'transparency_index') }} p using (jurisdiction)
where abs(d.index_0_100 - p.index_0_100) > 0.1
