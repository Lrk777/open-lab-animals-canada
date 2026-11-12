with keyed as (
    select
        cast(year as integer) as year,
        animal_type,
        species,
        scientific_name,
        lower(trim(regexp_replace(coalesce(scientific_name, species), '\s+', ' ', 'g'))) as species_key,
        cast(n_animals as bigint) as n_animals
    from {{ source('raw', 'ccac_species_year') }}
)

select
    k.*,
    x.canonical_label,
    split_part(coalesce(k.scientific_name, 'Unspecified'), ' ', 1) as genus
from keyed k
left join {{ source('raw', 'ccac_species_crosswalk') }} x
    on x.animal_type = k.animal_type
    and x.species_key = k.species_key
    and x.species = k.species
