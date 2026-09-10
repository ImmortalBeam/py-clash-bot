"""Play Again GUI setting: job config entry, persistence keys and job-dictionary mapping."""

from __future__ import annotations

from pyclashbot.__main__ import make_job_dictionary
from pyclashbot.interface.config import JOBS, USER_CONFIG_KEYS
from pyclashbot.interface.enums import UIField


def _play_again_job():
    matches = [job for job in JOBS if job.key == UIField.PLAY_AGAIN_USER_TOGGLE]
    assert len(matches) == 1, "expected exactly one Play Again job entry"
    return matches[0]


def test_play_again_job_is_off_by_default_with_five_fights() -> None:
    job = _play_again_job()
    assert job.default is False
    extra = job.extras[UIField.MAX_PLAY_AGAIN_SELECTION]
    assert extra.default == 5
    assert min(extra.values) >= 1


def test_play_again_settings_are_persisted() -> None:
    assert UIField.PLAY_AGAIN_USER_TOGGLE.value in USER_CONFIG_KEYS
    assert UIField.MAX_PLAY_AGAIN_SELECTION.value in USER_CONFIG_KEYS


def test_job_dictionary_carries_play_again_settings() -> None:
    values = {
        UIField.PLAY_AGAIN_USER_TOGGLE.value: True,
        UIField.MAX_PLAY_AGAIN_SELECTION.value: "7",
    }
    jobs = make_job_dictionary(values)
    assert jobs[UIField.PLAY_AGAIN_USER_TOGGLE.value] is True
    assert jobs[UIField.MAX_PLAY_AGAIN_SELECTION.value] == 7


def test_job_dictionary_defaults_when_settings_missing() -> None:
    jobs = make_job_dictionary({})
    assert jobs[UIField.PLAY_AGAIN_USER_TOGGLE.value] is False
    assert jobs[UIField.MAX_PLAY_AGAIN_SELECTION.value] == 5
