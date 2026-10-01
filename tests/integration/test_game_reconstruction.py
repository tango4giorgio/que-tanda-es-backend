import json
import os
from uuid import uuid4

import pytest

from src.handlers.get_game import lambda_handler as get_game_handler
from src.handlers.get_previews import lambda_handler as get_previews_handler
from src.handlers.submit_feedback import lambda_handler as submit_feedback_handler
from src.repositories.db import connection

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL is required for Postgres integration tests",
)


def _seed_artist_with_playable_track(conn, display_name: str) -> None:
    with conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO artist (display_name) VALUES (%s) RETURNING id",
            (display_name,),
        )
        (artist_id,) = cursor.fetchone()
        cursor.execute(
            "INSERT INTO track (artist_id) VALUES (%s) RETURNING id",
            (str(artist_id),),
        )
        (track_id,) = cursor.fetchone()
        cursor.execute(
            """
            INSERT INTO track_provider (track_id, provider, provider_track_id, duration_ms)
            VALUES (%s, 'deezer', %s, 180000)
            """,
            (str(track_id), f"item-{uuid4().hex}"),
        )


def _game_event(query: str = "") -> dict:
    return {
        "version": "2.0",
        "routeKey": "GET /game",
        "rawPath": "/game",
        "rawQueryString": query,
        "requestContext": {"stage": "$default", "http": {"method": "GET", "path": "/game"}},
    }


def _feedback_event(body: dict) -> dict:
    return {
        "version": "2.0",
        "routeKey": "POST /feedback",
        "rawPath": "/feedback",
        "rawQueryString": "",
        "requestContext": {"stage": "$default", "http": {"method": "POST", "path": "/feedback"}},
        "body": json.dumps(body),
        "isBase64Encoded": False,
    }


def _previews_event(track_ids: list[str]) -> dict:
    return {
        "version": "2.0",
        "routeKey": "POST /previews",
        "rawPath": "/previews",
        "rawQueryString": "",
        "requestContext": {
            "stage": "$default",
            "http": {"method": "POST", "path": "/previews"},
        },
        "body": json.dumps({"trackIds": track_ids}),
        "isBase64Encoded": False,
    }


def test_a_full_game_is_reconstructable_from_persisted_records_alone() -> None:
    with connection() as conn:
        for index in range(4):
            _seed_artist_with_playable_track(conn, f"Test Orchestra {uuid4().hex[:8]}-{index}")

    response = get_game_handler(_game_event(), None)
    assert response["statusCode"] == 200
    payload = json.loads(response["body"])
    game_id = payload["gameId"]
    assert len(payload["rounds"]) == 3
    all_questions = [round_["question"] for round_ in payload["rounds"]]
    all_track_ids = [
        track_id for question in all_questions for track_id in question["trackIds"]
    ]
    preview_response = get_previews_handler(
        _previews_event(all_track_ids), None
    )
    assert preview_response["statusCode"] == 200
    previews = json.loads(preview_response["body"])["previews"]
    assert [preview["trackId"] for preview in previews] == [
        track_id for track_id in all_track_ids
    ]
    assert all(preview["previewUrl"].startswith("https://") for preview in previews)

    for question in all_questions:
        for track_position in range(1, len(question["trackIds"]) + 1):
            feedback_response = submit_feedback_handler(
                _feedback_event(
                    {
                        "questionId": question["questionId"],
                        "trackPosition": track_position,
                        "guessedArtistId": None,
                        "outcome": "skipped",
                        "elapsedMs": 5000,
                    }
                ),
                None,
            )
            assert feedback_response["statusCode"] == 202

        feedback_response = submit_feedback_handler(
            _feedback_event(
                {
                    "questionId": question["questionId"],
                    "trackPosition": 1,
                    "guessedArtistId": None,
                    "outcome": "skipped",
                    "elapsedMs": 5000,
                }
            ),
            None,
        )
        assert feedback_response["statusCode"] == 400

    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM game_round WHERE game_id = %s",
                (game_id,),
            )
            (round_count,) = cursor.fetchone()
            assert round_count == 3

            cursor.execute(
                """
                SELECT gr.sequence_number, q.id, q.track_ids, q.artist_ids
                FROM game_round AS gr
                JOIN round_question AS rq ON rq.round_id = gr.round_id
                JOIN question AS q ON q.id = rq.question_id
                WHERE gr.game_id = %s
                ORDER BY gr.sequence_number, rq.sequence_number
                """,
                (game_id,),
            )
            question_rows = cursor.fetchall()
            assert {row[0] for row in question_rows} == {1, 2, 3}
            assert all(len(row[2]) >= 1 for row in question_rows)
            assert all(len(row[3]) == 3 for row in question_rows)

            question_ids = [str(row[1]) for row in question_rows]
            cursor.execute(
                """
                SELECT question_id, track_position, outcome
                FROM guess_feedback
                WHERE question_id = ANY(%s::uuid[])
                """,
                (question_ids,),
            )
            feedback_rows = cursor.fetchall()
            assert {str(row[0]) for row in feedback_rows} == set(question_ids)
            assert all(row[2] == "skipped" for row in feedback_rows)
