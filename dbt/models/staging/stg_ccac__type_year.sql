select
    cast(year as integer) as year,
    animal_type,
    cast(n_animals as bigint) as n_animals,
    year >= 2012 as comparable_series
from {{ source('raw', 'ccac_type_year') }}
