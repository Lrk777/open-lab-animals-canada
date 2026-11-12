-- One row per year: Canadian nonhuman-primate counts with composition shares.
with totals as (
    select year, n_animals as nhp_animals, comparable_series
    from {{ ref('stg_ccac__type_year') }}
    where animal_type = 'Nonhuman primates'
),

uses as (
    select
        year,
        sum(n_uses) as nhp_uses,
        sum(case when genus_is_macaque then n_uses end) as macaque_uses,
        sum(case when ci in ('D', 'E') then n_uses end) as ci_d_e_uses,
        sum(case when pau = 1 then n_uses end) as pau1_fundamental_uses,
        sum(case when pau = 3 then n_uses end) as pau3_regulatory_uses
    from (
        select *, coalesce(scientific_name, '') like 'Macaca %' as genus_is_macaque
        from {{ ref('stg_ccac__species_ci_pau') }}
        where animal_type = 'Nonhuman primates'
    )
    group by year
),

rhesus as (
    select year, sum(n_animals) as rhesus_animals
    from {{ ref('stg_ccac__species_year') }}
    where scientific_name = 'Macaca mulatta'
    group by year
)

select
    t.year,
    t.comparable_series,
    t.nhp_animals,
    r.rhesus_animals,
    u.nhp_uses,
    round(u.macaque_uses / u.nhp_uses, 3) as macaque_share,
    round(u.ci_d_e_uses / u.nhp_uses, 3) as ci_d_e_share,
    round(u.pau1_fundamental_uses / u.nhp_uses, 3) as fundamental_share,
    round(u.pau3_regulatory_uses / u.nhp_uses, 3) as regulatory_share,
    round(t.nhp_animals / lag(t.nhp_animals) over (order by t.year) - 1, 3) as yoy_change
from totals t
left join uses u using (year)
left join rhesus r using (year)
order by t.year
