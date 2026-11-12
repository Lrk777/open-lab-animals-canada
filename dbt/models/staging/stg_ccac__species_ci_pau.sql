with src as (
    select * from {{ source('raw', 'ccac_species_ci_pau') }}
),

keyed as (
    select
        cast(year as integer) as year,
        animal_type,
        species,
        scientific_name,
        lower(trim(regexp_replace(coalesce(scientific_name, species), '\s+', ' ', 'g'))) as species_key,
        upper(ci) as ci,
        cast(pau as integer) as pau,
        cast(n_animals as bigint) as n_uses
    from src
)

select
    k.*,
    x.canonical_label
from keyed k
left join {{ source('raw', 'ccac_species_crosswalk') }} x
    on x.animal_type = k.animal_type
    and x.species_key = k.species_key
    and x.species = k.species
