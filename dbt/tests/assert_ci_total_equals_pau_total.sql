-- The invasiveness table and the purpose table describe the same animals, so their yearly totals
-- must be equal. Any returned row is a contradiction in the published CCAC report.
with ci as (select year, sum(n_animals) as n from {{ source('raw', 'ccac_ci_year') }} group by year),
     pau as (select year, sum(n_animals) as n from {{ source('raw', 'ccac_pau_year') }} group by year)
select ci.year, ci.n as ci_total, pau.n as pau_total
from ci join pau using (year)
where ci.n <> pau.n
