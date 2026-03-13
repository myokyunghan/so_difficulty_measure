from datetime import datetime, timedelta

def generate_4week_timestamps(std_date, year_range_str):

    from_year, to_year = map(int, year_range_str.split("to"))
    std_year = std_date.year

    start_date = std_date - timedelta(weeks=52 * (std_year - from_year))
    end_date = std_date + timedelta(weeks=52 * (to_year - std_year))

    timestamps = []
    current = start_date

    while current <= end_date:
        timestamps.append(current.strftime("%Y.%m.%d"))
        current += timedelta(days=28)

    return {
        "start_date": start_date,
        "std_date": std_date,
        "end_date": end_date,
        "monthly_timestamps": timestamps
    }


Date_Setting = {
    "2019to2021": generate_4week_timestamps(datetime(2020,11,30), "2019to2021"),
    "2020to2022": generate_4week_timestamps(datetime(2021,11,30), "2020to2022"),
    "2021to2023": generate_4week_timestamps(datetime(2022,11,30), "2021to2023"),
    "2022to2024": generate_4week_timestamps(datetime(2023,11,30), "2022to2024"),
    "2023to2025": generate_4week_timestamps(datetime(2024,11,30), "2023to2025"),

    "2021to2024": generate_4week_timestamps(datetime(2022,11,30), "2021to2024"),
    "2021to2025": generate_4week_timestamps(datetime(2022,11,30), "2021to2025"),

    "2020to2025": generate_4week_timestamps(datetime(2022,11,30), "2020to2025"),
}