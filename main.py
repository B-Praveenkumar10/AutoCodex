import os
from github import Github
import google.generativeai as genai
import re
from datetime import datetime
import javalang
import ast
import radon.metrics as metrics
from radon.complexity import cc_visit
from pylint.lint import Run
from pylint.reporters import JSONReporter
import subprocess
import json
from typing import Dict, List, Union
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import tempfile


class AdvancedCodeReviewBot:
    def __init__(self, github_token: str, gemini_api_key: str):
        self.github = Github(github_token)
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        self.tfidf = TfidfVectorizer()
        self.rules = self._load_rules()

    def _load_rules(self) -> Dict:
        return {
            'python': {
                'max_line_length': 100,
                'max_function_length': 50,
                'max_complexity': 10,
                'min_test_coverage': 80,
                'naming_conventions': {
                    'class': r'^[A-Z][a-zA-Z0-9]*$',
                    'function': r'^[a-z][a-z0-9_]*$',
                    'variable': r'^[a-z][a-z0-9_]*$',
                    'constant': r'^[A-Z][A-Z0-9_]*$'
                }
            },
            'java': {
                'max_line_length': 120,
                'max_function_length': 60,
                'max_complexity': 15,
                'min_test_coverage': 85,
                'naming_conventions': {
                    'class': r'^[A-Z][a-zA-Z0-9]*$',
                    'method': r'^[a-z][a-zA-Z0-9]*$',
                    'variable': r'^[a-z][a-z0-9]*$',
                    'constant': r'^[A-Z][A-Z0-9_]*$'
                }
            }
        }

    def _run_pylint(self, code: str) -> float:
        # Create a temporary file to store the code
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_file:
            temp_file.write(code)
            temp_file_path = temp_file.name

        try:
            # Create a JSON reporter
            reporter = JSONReporter()

            # Run pylint with the JSON reporter
            Run([temp_file_path], reporter=reporter, exit=False)

            # Get the score from the reporter
            if reporter.messages:
                # Calculate score based on messages (10 - number of errors/warnings)
                score = max(0.0, 10.0 - (len(reporter.messages) * 0.1))
            else:
                score = 10.0

            return score

        finally:
            # Clean up the temporary file
            os.unlink(temp_file_path)

    def calculate_metrics(self, code: str, language: str) -> Dict:
        metrics_result = {
            'loc': len(code.splitlines()),
            'complexity': 0,
            'maintainability': 0,
            'test_coverage': 0,
            'duplication': 0
        }

        try:
            if language == 'python':
                # Calculate cyclomatic complexity
                metrics_result['complexity'] = max(
                    (cc.complexity for cc in cc_visit(code)), default=0
                )

                # Calculate maintainability index
                mi = metrics.mi_visit(code, multi=True)
                metrics_result['maintainability'] = mi

                # Run pylint for additional metrics
                metrics_result['pylint_score'] = self._run_pylint(code)

            elif language == 'java':
                # Check if PMD is available
                try:
                    # Use PMD for Java metrics if available
                    with open('temp.java', 'w') as f:
                        f.write(code)
                    process = subprocess.run(
                        ['pmd', '-d', 'temp.java', '-f', 'json', '-R', 'rulesets/java/quickstart.xml'],
                        capture_output=True, text=True
                    )
                    os.remove('temp.java')

                    if process.stdout:
                        pmd_results = json.loads(process.stdout)
                        metrics_result['pmd_violations'] = len(pmd_results.get('files', []))
                except FileNotFoundError:
                    #print("PMD not found. Skipping Java-specific metrics.")
                    # Provide basic metrics without PMD
                    metrics_result['complexity'] = len(re.findall(r'\b(if|for|while|switch)\b', code))
                    metrics_result['maintainability'] = 50  # Default value

            # Calculate code duplication using cosine similarity
            lines = code.splitlines()
            if len(lines) > 1:
                vectors = self.tfidf.fit_transform(lines)
                similarity_matrix = cosine_similarity(vectors)
                metrics_result['duplication'] = (
                        (np.sum(similarity_matrix > 0.8) - len(lines)) / 2
                )

        except Exception as e:
            print(f"Error calculating metrics: {str(e)}")

        return metrics_result

    def analyze_code_quality(self, code: str, language: str) -> Dict:
        issues = []

        # Common analysis for both languages
        metrics_result = self.calculate_metrics(code, language)

        if metrics_result['complexity'] > self.rules[language]['max_complexity']:
            issues.append(
                f"High cyclomatic complexity: {metrics_result['complexity']} " +
                f"(max: {self.rules[language]['max_complexity']})"
            )

        if metrics_result['duplication'] > 10:
            issues.append(f"High code duplication detected: {metrics_result['duplication']}%")

        # Language-specific analysis
        if language == 'python':
            issues.extend(self._analyze_python(code))
        else:
            issues.extend(self._analyze_java(code))

        return {
            'issues': issues,
            'metrics': metrics_result,
            'total_issues': len(issues)
        }

    def _analyze_python(self, code: str) -> List[str]:
        issues = []
        try:
            tree = ast.parse(code)

            # Advanced Python-specific checks
            for node in ast.walk(tree):
                # Type hint checks
                if isinstance(node, ast.FunctionDef):
                    if not node.returns and not any(
                            isinstance(a, ast.AnnAssign) for a in node.args.args
                    ):
                        issues.append(f"Missing type hints in function {node.name}")

                # Security checks
                if isinstance(node, ast.Call):
                    if getattr(node.func, 'id', '') in ['eval', 'exec']:
                        issues.append(f"Potentially unsafe use of {node.func.id}")

                # Performance checks
                if isinstance(node, ast.ListComp):
                    parent = next(ast.walk(tree))
                    if isinstance(parent, ast.For):
                        issues.append("Consider using generator expression for memory efficiency")

        except Exception as e:
            issues.append(f"Python analysis error: {str(e)}")

        return issues

    def _analyze_java(self, code: str) -> List[str]:
        issues = []
        try:
            tree = javalang.parse.parse(code)

            # Advanced Java-specific checks
            for path, node in tree:
                # Check for proper exception handling
                if isinstance(node, javalang.tree.TryStatement):
                    if not node.finally_block and not node.resources:
                        issues.append("Consider adding finally block or try-with-resources")

                # Check for immutability
                if isinstance(node, javalang.tree.FieldDeclaration):
                    if 'final' not in node.modifiers:
                        issues.append(f"Consider making field {node.declarators[0].name} final")

                # Check for builder pattern usage
                if isinstance(node, javalang.tree.ClassDeclaration):
                    if len(node.fields) > 5 and not any(
                            m.name == 'builder' for m in node.methods
                    ):
                        issues.append("Consider implementing Builder pattern")

        except Exception as e:
            issues.append(f"Java analysis error: {str(e)}")

        return issues

    def get_ai_suggestions(self, code: str, language: str, metrics: Dict) -> str:
        prompt = f"""Analyze this {language} code with metrics:
        - Complexity: {metrics['complexity']}
        - Maintainability: {metrics['maintainability']}
        - LOC: {metrics['loc']}

        Provide specific suggestions for:
        1. Code optimization
        2. Design patterns
        3. Best practices
        4. Security improvements

        Code: {code}"""

        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"AI review failed: {str(e)}"

    def process_repository(self, repo_name: str) -> Dict:
        try:
            repo = self.github.get_repo(repo_name)
            results = {
                'repository': repo_name,
                'scan_date': datetime.now().isoformat(),
                'files_analyzed': 0,
                'total_issues': 0,
                'file_results': {},
                'overall_metrics': {
                    'avg_complexity': 0,
                    'avg_maintainability': 0,
                    'total_loc': 0,
                    'quality_score': 0
                }
            }

            contents = repo.get_contents("")
            while contents:
                file_content = contents.pop(0)
                if file_content.type == "dir":
                    contents.extend(repo.get_contents(file_content.path))
                elif file_content.path.endswith(('.py', '.java')):
                    language = 'python' if file_content.path.endswith('.py') else 'java'

                    try:
                        code = file_content.decoded_content.decode('utf-8')
                        analysis = self.analyze_code_quality(code, language)
                        metrics = analysis['metrics']

                        results['file_results'][file_content.path] = {
                            'language': language,
                            'issues': analysis['issues'],
                            'metrics': metrics,
                            'ai_suggestions': self.get_ai_suggestions(code, language, metrics)
                        }

                        # Update overall metrics
                        results['overall_metrics']['avg_complexity'] += metrics['complexity']
                        results['overall_metrics']['total_loc'] += metrics['loc']
                        results['total_issues'] += analysis['total_issues']
                        results['files_analyzed'] += 1

                        print(f"Analyzed {language} file: {file_content.path}")
                    except Exception as e:
                        print(f"Error processing {file_content.path}: {str(e)}")

            # Calculate final averages
            if results['files_analyzed'] > 0:
                results['overall_metrics']['avg_complexity'] /= results['files_analyzed']
                results['overall_metrics']['quality_score'] = self._calculate_quality_score(
                    results['overall_metrics']
                )

            return results
        except Exception as e:
            return {
                'repository': repo_name,
                'error': str(e),
                'files_analyzed': 0,
                'total_issues': 0
            }

    def _calculate_quality_score(self, metrics: Dict) -> float:
        # Calculate a quality score between 0-100
        weights = {
            'complexity': 0.3,
            'maintainability': 0.3,
            'issues_density': 0.4
        }

        try:
            complexity_score = max(0, 100 - (metrics['avg_complexity'] * 5))
            maintainability_score = metrics.get('avg_maintainability', 50)
            issues_density = min(100, (metrics['total_issues'] / metrics['total_loc']) * 1000)

            return (
                    weights['complexity'] * complexity_score +
                    weights['maintainability'] * maintainability_score +
                    weights['issues_density'] * (100 - issues_density)
            )
        except:
            return 0

    def generate_report(self, results: Dict, output_file: str = "code_review_report.md"):
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# Code Review Analysis Report\n\n")
            f.write(f"## Repository: {results['repository']}\n")
            f.write(f"Analysis Date: {results['scan_date']}\n\n")

            f.write("## Overall Metrics\n")
            f.write(f"- Files Analyzed: {results['files_analyzed']}\n")
            f.write(f"- Total Issues: {results['total_issues']}\n")
            f.write(f"- Average Complexity: {results['overall_metrics']['avg_complexity']:.2f}\n")
            f.write(f"- Quality Score: {results['overall_metrics']['quality_score']:.2f}/100\n\n")

            f.write("## Detailed Analysis\n\n")
            for filename, data in results['file_results'].items():
                f.write(f"### {filename}\n")
                f.write(f"Language: {data['language']}\n\n")

                f.write("#### Metrics\n")
                for metric, value in data['metrics'].items():
                    f.write(f"- {metric}: {value}\n")

                if data['issues']:
                    f.write("\n#### Issues\n")
                    for issue in data['issues']:
                        f.write(f"- {issue}\n")

                f.write("\n#### AI Suggestions\n")
                f.write(data['ai_suggestions'])
                f.write("\n\n---\n\n")


def main():
    # Replace these with your actual tokens
    GITHUB_TOKEN = "GITHUB_TOKEN"
    GEMINI_API_KEY = "GEMINI_API_KEY"
    REPO_NAME = "B-Praveenkumar10/testrepo"

    bot = AdvancedCodeReviewBot(GITHUB_TOKEN, GEMINI_API_KEY)
    results = bot.process_repository(REPO_NAME)

    bot.generate_report(results)
    print("\nAnalysis complete! Check code_review_report.md for detailed results.")


if __name__ == "__main__":
    main()