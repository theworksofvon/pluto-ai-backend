import pandas as pd


# ------------------------------
# UTILITY METHODS
# ------------------------------


def save_to_csv(data: pd.DataFrame, filename: str):
    """
    Save data to a CSV file.

    Args:
        data (pd.DataFrame): DataFrame to save.
        filename (str): File path for saving the data.
    """
    data.to_csv(filename, index=False)
    print(f"Data saved to {filename}")


def load_from_csv(filename: str) -> pd.DataFrame:
    """
    Load data from a CSV file.

    Args:
        filename (str): Path to the CSV file.

    Returns:
        pd.DataFrame: Loaded data.
    """
    return pd.read_csv(filename)
