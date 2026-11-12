with s as (
    select * from {{ ref('stg_transparency__scores') }}
)

select
    jurisdiction,
    round(100 * sum(score * weight) / (3 * sum(weight)), 1) as index_0_100,
    count(*) as n_dimensions,
    sum(case when status = 'to_verify' then 1 else 0 end) as unverified_cells,
    rank() over (order by sum(score * weight) / sum(weight) desc) as rank
from s
group by jurisdiction
