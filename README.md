# Advanced Code Review Bot

The **Advanced Code Review Bot** is a Python-based tool designed to analyze code quality in GitHub repositories. It supports both Python and Java projects by measuring key metrics such as cyclomatic complexity, maintainability, and code duplication. In addition, the bot leverages static analysis tools (like PyLint and PMD) and generative AI (via Gemini-2.0 Flash) to provide actionable code improvement suggestions.

## Features

- **Multi-language Support**: Analyzes both Python and Java source code.
- **Metrics Calculation**:
  - **Python**: Uses [radon](https://radon.readthedocs.io/en/latest/) for cyclomatic complexity and maintainability index, and [PyLint](https://www.pylint.org/) for additional static analysis.
  - **Java**: Uses [PMD](https://pmd.github.io/) (if available) for identifying code issues; falls back to regex-based checks when PMD is not installed.
  - **Duplication Detection**: Computes code duplication using TF-IDF and cosine similarity.
- **Advanced Code Analysis**: Provides language-specific checks such as type hint verification and secure coding practices.
- **AI-Powered Suggestions**: Uses the Gemini generative model to offer recommendations on code optimization, design patterns, best practices, and security improvements.
- **Automated Reporting**: Generates a comprehensive Markdown report summarizing the analysis and suggestions.

## Prerequisites

- **Python 3.7+**  
- **GitHub API Token**: Obtain a personal access token from GitHub to allow repository access.  
- **Gemini API Key**: Required for the generative AI suggestions (configured via the `google.generativeai` package).

### Additional Tools (Optional)

- **PMD**: For enhanced Java code analysis, install PMD and ensure it is available in your system's PATH.

## Installation

1. **Clone the Repository**

   ```bash
   git clone https://github.com/yourusername/advanced-code-review-bot.git
   cd advanced-code-review-bot
   ```

2. **Create a Virtual Environment (Recommended)**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install Dependencies**

   Ensure you have a requirements.txt file listing the following packages (adjust versions as needed):

   ```text
   PyGithub
   google-generativeai
   radon
   pylint
   javalang
   scikit-learn
   numpy
   ```

   Then run:

   ```bash
   pip install -r requirements.txt
   ```

## Configuration

Before running the bot, update the following values in the main() function of your Python script:

- GitHub Token: Replace the placeholder in GITHUB_TOKEN with your GitHub personal access token.
- Gemini API Key: Replace the placeholder in GEMINI_API_KEY with your Gemini API key.
- Repository Name: Set the REPO_NAME variable to the full name (e.g., username/repository) of the GitHub repository you want to analyze.

## Usage

Once configured, you can run the bot using:

```bash
python main.py
```

After execution, the bot will:

1. Clone and traverse the specified repository.
2. Analyze each Python and Java file based on predefined rules.
3. Compute various metrics (e.g., complexity, maintainability, duplication).
4. Generate AI-based improvement suggestions.
5. Produce a detailed Markdown report named code_review_report.md in the project directory.

Open the code_review_report.md file to view the analysis and recommendations.

## Customization

- **Rules and Metrics**: The analysis rules (e.g., maximum line length, function length, complexity thresholds) are defined within the _load_rules() method. Adjust these to suit your coding standards.
- **AI Prompt**: Modify the prompt in the get_ai_suggestions() method to tailor the AI-generated feedback.
- **Additional Analyses**: Extend the _analyze_python() or _analyze_java() methods to add further checks or integrate with other static analysis tools.

## Troubleshooting

- **PMD Not Found (Java Analysis)**: If PMD is not installed or not in your PATH, the bot will skip PMD-specific checks for Java files and apply basic metrics instead.
- **API Issues**: Verify your GitHub token and Gemini API key are correct and have the required permissions.

## Contributing

Contributions are welcome! Feel free to fork the repository and submit pull requests for enhancements or bug fixes.

## License

This project is licensed under the MIT License. See the LICENSE file for details.
