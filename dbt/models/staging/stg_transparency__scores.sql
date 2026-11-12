select
    jurisdiction,
    dimension,
    cast(score as integer) as score,
    cast(weight as double) as weight,
    status,
    evidence,
    question
from {{ source('raw', 'transparency_scores') }}
