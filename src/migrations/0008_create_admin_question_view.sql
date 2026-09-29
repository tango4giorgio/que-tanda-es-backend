CREATE OR REPLACE VIEW admin_question AS
SELECT
    q.id AS question_id,
    track_details.tracks,
    artist_details.artists,
    correct_artist.id AS correct_artist_id,
    correct_artist.display_name AS correct_artist_name,
    q.created_at,
    q.updated_at
FROM question AS q
CROSS JOIN LATERAL (
    SELECT
        jsonb_agg(
            jsonb_build_object(
                'trackId', t.id,
                'title', preferred_provider.title
            )
            ORDER BY track_entry.position
        ) AS tracks,
        (array_agg(t.artist_id ORDER BY track_entry.position))[1] AS correct_artist_id
    FROM jsonb_array_elements_text(q.track_ids)
        WITH ORDINALITY AS track_entry(track_id, position)
    JOIN track AS t ON t.id = track_entry.track_id::uuid
    LEFT JOIN LATERAL (
        SELECT tp.title
        FROM track_provider AS tp
        WHERE tp.track_id = t.id
          AND tp.title IS NOT NULL
        ORDER BY (tp.provider = 'deezer') DESC, tp.provider, tp.id
        LIMIT 1
    ) AS preferred_provider ON true
) AS track_details
CROSS JOIN LATERAL (
    SELECT jsonb_agg(
        jsonb_build_object(
            'artistId', a.id,
            'name', a.display_name
        )
        ORDER BY artist_entry.position
    ) AS artists
    FROM jsonb_array_elements_text(q.artist_ids)
        WITH ORDINALITY AS artist_entry(artist_id, position)
    JOIN artist AS a ON a.id = artist_entry.artist_id::uuid
) AS artist_details
JOIN artist AS correct_artist ON correct_artist.id = track_details.correct_artist_id;
