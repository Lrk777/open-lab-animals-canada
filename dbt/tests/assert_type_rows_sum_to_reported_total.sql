with s as (
    select year, sum(n_animals) as summed from {{ source('raw', 'ccac_type_year') }} group by year
)
select s.year, s.summed, t.reported_total
from s join {{ source('raw', 'ccac_reported_totals') }} t using (year)
where s.summed <> t.reported_total
