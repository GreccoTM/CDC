# Commander Deck Check (CDC) Project

## Project Overview

The "Commander Deck Check" (CDC) is a Python desktop application designed to assist Magic: The Gathering players in building Commander decks. The application aims to be cross-platform, supporting both Linux and Windows operating systems.

Its core functionalities include:
1.  **Commander Identification:** Users will provide a list of cards (either via plain text input or a file), and the application will identify eligible commanders from this list by consulting the local `AllPrintings.json` file.
2.  **EDHREC Integration:** For selected eligible commanders, the application will fetch recommended cards from the EDHREC website using their JSON API (e.g., `https://json.edhrec.com/pages/commanders/{creature-name}.json`).

The graphical user interface (GUI) for this application will be built using `Tkinter`, a standard Python library for creating desktop applications.

## Building and Running

To set up and run the Commander Deck Check application, follow these steps:

### Prerequisites

Ensure you have Python 3.x installed on your system.

### Installation

1.  **Navigate to the project directory:**
    ```bash
    cd /home/ice/Documentos/CDC/cdc
    ```
2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

### Running the Application

After installing the dependencies, you can run the application using the following command:

```bash
python cdc.py
```

## Development Conventions

As this is a new project, specific development conventions will be established as the codebase grows. However, the following are recommended:

*   **Code Formatting:** Use `black` for consistent code formatting.
*   **Linting:** Use `flake8` for linting to maintain code quality.
*   **Type Hinting:** Employ Python type hints for improved code readability and maintainability.

## Data Files

*   **`AllPrintings.json`**: This large JSON file contains comprehensive data for Magic: The Gathering cards. It is located in the root directory (`/home/ice/Documentos/CDC/`) and will be used by the application to identify card properties and eligibility for commander status. Due to its size, efficient parsing and querying of this file will be crucial.
