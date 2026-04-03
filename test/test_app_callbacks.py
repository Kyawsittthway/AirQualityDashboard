import sys
import os

sys.path.append(os.path.abspath("src"))
from utils.logics import toggle_threshold_logic, toggle_theme_logic, update_year_logic


# Unit Testing for toggling threshold
def test_toggle_threshold_uk():
    result = toggle_threshold_logic("toggle-uk", 1, 0)
    assert result == ("toggle-option active", "toggle-option", "UK")


def test_toggle_threshold_who():
    result = toggle_threshold_logic("toggle-who", 0, 1)
    assert result == ("toggle-option", "toggle-option active", "WHO")


def test_toggle_threshold_default():
    result = toggle_threshold_logic(None, None, None)
    assert result == ("toggle-option active", "toggle-option", "UK")


# Unit Testing for toggling themes
def test_toggle_theme_dark():
    result = toggle_theme_logic(1, 0, "toggle-dark")
    assert result == ("toggle-option active", "toggle-option", "dark", "dark")


def test_toggle_theme_light():
    result = toggle_theme_logic(0, 1, "toggle-light")
    assert result == ("toggle-option", "toggle-option active", "light", "light")


def test_toggle_theme_default():
    result = toggle_theme_logic(None, None, None)
    assert result == ("toggle-option active", "toggle-option", "dark", "dark")


# Unit Testing for updating year

# tests/test_year_dropdown.py


def test_update_year_no_selection():
    """Test when nothing selected"""
    result = update_year_logic(
        sites=None,
        pollutant=None,
        current_years=None,
        all_years=[2020, 2021, 2022, 2023, 2024, 2025],
        site_to_years={...},
        pollutant_to_years={...},
        site_pollutant_to_years={...},
    )

    assert len(result) == 6
    assert result[0]["value"] == 2020
