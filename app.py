import streamlit as st
import requests
import base64
import os
import google.generativeai as genai
from dotenv import load_dotenv
import json
import re
import pandas as pd
import time

# Load environment variables
load_dotenv()

# Set page configuration
st.set_page_config(
    page_title="AutoCodex",
    page_icon="🔍",
    layout="wide"
)

# Define the guidelines
JAVA_GUIDELINES = """
Guidelines for Java code reviews:
1. Follow Java code conventions (package names in lowercase, constants in all caps, variable names in CamelCase)
2. Replace imperative code with lambdas and streams when using Java 8+
3. Beware of the NullPointerException, avoid returning nulls, use Optional class
4. Avoid directly assigning references from client code to a field
5. Handle exceptions with care, ensure catch blocks are from most specific to least
6. Use appropriate data structures (Map, List, Set)
7. Be cautious with access modifiers, keep methods private by default
8. Code to interfaces rather than concrete implementations
9. Don't force fit interfaces when not necessary
10. Override hashCode when overriding equals
"""

# Initialize API keys from environment variables
@st.cache_resource
def load_api_keys():
    github_token = os.getenv("GITHUB_TOKEN")
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    
    if not github_token or not gemini_api_key:
        st.error("API keys not found. Please make sure they are properly set in the environment.")
        st.stop()
    
    return {
        "github_token": github_token,
        "gemini_api_key": gemini_api_key
    }

# Initialize Gemini API
@st.cache_resource
def initialize_gemini(api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    return model

# Function to get Java files from a GitHub repo
def get_java_files(repo_name, github_token):
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Get default branch
    url = f"https://api.github.com/repos/{repo_name}"
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        return None, f"Error accessing repository: {response.json().get('message', '')}"
    
    default_branch = response.json().get("default_branch", "main")
    
    # Get all files in the repo using the default branch
    url = f"https://api.github.com/repos/{repo_name}/git/trees/{default_branch}?recursive=1"
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        return None, f"Error fetching repository files: {response.json().get('message', '')}"
    
    tree = response.json().get("tree", [])
    java_files = [item for item in tree if item["path"].endswith(".java")]
    
    if not java_files:
        return None, "No Java files found in the repository."
    
    return java_files, None

# Function to get file content
def get_file_content(repo_name, file_path, github_token):
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    url = f"https://api.github.com/repos/{repo_name}/contents/{file_path}"
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        return None, f"Error fetching file content: {response.json().get('message', '')}"
    
    content = response.json()["content"]
    decoded_content = base64.b64decode(content).decode('utf-8')
    
    return decoded_content, None

# Function to analyze code with Gemini
def analyze_code_with_gemini(code, file_path, model):
    prompt = f"""
You are a Java code review expert. Analyze the following Java code from file '{file_path}' against these guidelines:

{JAVA_GUIDELINES}

For each guideline, provide:
1. Whether the code follows or violates the guideline (use EXACTLY "followed", "violated", or "not applicable")
2. Specific examples from the code
3. Suggested modifications to fix violations

Return ONLY a valid, parseable JSON object with this structure:
{{
  "summary": "Brief overall assessment",
  "guidelines_analysis": [
    {{
      "guideline_number": 1,
      "guideline_description": "Follow Java code conventions",
      "status": "followed" or "violated" or "not applicable",
      "details": "Explanation with examples from code",
      "modifications": "Suggested code changes if violated or null if followed"
    }},
    ...
  ]
}}

No preamble, explanation, or code blocks around the JSON. Ensure the JSON is valid and properly escaped.

Here's the code to analyze:

{code}
"""

    try:
        generation = model.generate_content(prompt)
        return generation.text.strip()
    except Exception as e:
        return f"Error generating analysis: {str(e)}"

# Improved function to parse Gemini's response and extract the JSON
def parse_gemini_response(response_text):
    # Remove any markdown code block markers
    cleaned_text = re.sub(r'```json|```', '', response_text).strip()
    
    # Try to parse the cleaned text directly first
    try:
        return json.loads(cleaned_text)
    except json.JSONDecodeError:
        # Look for a JSON object with more careful pattern matching
        try:
            # Find the opening brace of the JSON object
            start_idx = cleaned_text.find('{')
            if start_idx == -1:
                raise ValueError("No JSON object found")
                
            # Track nested braces to find the matching closing brace
            brace_count = 0
            for i in range(start_idx, len(cleaned_text)):
                if cleaned_text[i] == '{':
                    brace_count += 1
                elif cleaned_text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        # Found the matching closing brace
                        json_str = cleaned_text[start_idx:i+1]
                        return json.loads(json_str)
            
            raise ValueError("No complete JSON object found")
        except Exception:
            # If extraction fails, return structured error data
            return {
                "summary": "Error parsing AI response",
                "guidelines_analysis": [
                    {
                        "guideline_number": i,
                        "guideline_description": f"Guideline {i}",
                        "status": "unknown",
                        "details": "Failed to parse AI analysis",
                        "modifications": None
                    } for i in range(1, 11)
                ]
            }

# CSS for styling
def load_css():
    st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        color: #0066cc;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #333;
        margin-bottom: 1rem;
    }
    .file-header {
        font-size: 1.2rem;
        color: #2c3e50;
        background-color: #ecf0f1;
        padding: 0.5rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
    .guideline-header {
        font-size: 1.1rem;
        font-weight: bold;
        margin-top: 0.8rem;
    }
    .followed {
        color: #27ae60;
        font-weight: bold;
    }
    .violated {
        color: #e74c3c;
        font-weight: bold;
    }
    .unknown {
        color: #f39c12;
        font-weight: bold;
    }
    .details {
        margin-left: 1rem;
        padding-left: 0.5rem;
        border-left: 2px solid #bdc3c7;
        margin-bottom: 0;  /* Remove bottom margin */
    }
    code {
        white-space: pre-wrap !important;
        word-break: break-word !important;
    }
    .stCodeBlock {
        max-width: 100%;
    }
    .stCodeBlock pre {
        white-space: pre-wrap !important;
        word-wrap: break-word !important;
    }
    .summary-box {
        background-color: #f0f8ff;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
        border-left: 4px solid #0066cc;
    }
    .code-sample {
        font-family: monospace;
        background-color: #f7f7f7;
        padding: 0.2rem;
        border-radius: 3px;
    }
    .stProgress > div > div > div > div {
        background-color: #0066cc;
    }
    .stats-card {
        background-color: white;
        border-radius: 5px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        padding: 1rem;
        margin: 0.5rem;
        text-align: center;
    }
    .stats-number {
        font-size: 2rem;
        font-weight: bold;
        color: #0066cc;
    }
    .stats-label {
        font-size: 0.9rem;
        color: #666;
    }
    .file-progress-circle {
        width: 30px;
        height: 30px;
        margin: 0 auto;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .file-progress-circle.success {
        background-color: #27ae60;
        color: white;
        font-weight: bold;
        font-size: 18px;
    }
    .file-progress-circle.error {
        background-color: #e74c3c;
        color: white;
        font-weight: bold;
        font-size: 18px;
    }
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    .loading-spinner {
        border: 4px solid #f3f3f3;
        border-top: 4px solid #0066cc;
        border-radius: 50%;
        width: 20px;
        height: 20px;
        animation: spin 1s linear infinite;
    }
    .guidelines-chart {
        width: 100%;
        height: 300px;
    }
    </style>
    """, unsafe_allow_html=True)

# Generate a simple chart for guideline compliance
def generate_compliance_chart(summary_data):
    # Format data for visualization
    chart_data = []
    for row in summary_data:
        guideline_num = int(row["Guideline"].split()[1])
        followed = row["Followed"]
        violated = row["Violated"]
        total = followed + violated
        
        chart_data.append({
            "guideline": f"G{guideline_num}",
            "followed": followed,
            "violated": violated,
            "total": total,
            "compliance": followed / total if total > 0 else 0
        })
    
    df = pd.DataFrame(chart_data)
    df = df.sort_values("compliance")
    
    # Create a horizontal bar chart
    st.bar_chart(
        df.set_index("guideline")["compliance"],
        use_container_width=True,
        height=300
    )
def format_file_path(path, max_length=50):
    """Format a file path for display by shortening it if needed"""
    if len(path) <= max_length:
        return path
        
    # Split the path to get filename and directory
    parts = path.split('/')
    filename = parts[-1]
    
    # If just the filename is too long, truncate it
    if len(filename) > max_length - 5:
        return f".../{filename[:max_length-10]}..."
        
    # Otherwise keep the filename intact and truncate the path
    path_length = max_length - len(filename) - 5
    return f".../{'/'.join(parts[-2:-1])}/{filename}"
# Add this function before main()
def update_file_progress(placeholder, progress_percent, status="in_progress"):
    """
    Update file progress indicator with loading circle or completion status
    status: 'in_progress', 'success', or 'error'
    """
    # Clear the placeholder first to remove any existing content
    placeholder.empty()
    
    if status == "in_progress":
        # Show loading circle
        placeholder.markdown(f"""
        <div class="file-progress-circle">
            <div class="loading-spinner"></div>
        </div>
        """, unsafe_allow_html=True)
    elif status == "success":
        # Show success checkmark
        placeholder.markdown(f"""
        <div class="file-progress-circle success">
            <span>✓</span>
        </div>
        """, unsafe_allow_html=True)
    elif status == "error":
        # Show error X
        placeholder.markdown(f"""
        <div class="file-progress-circle error">
            <span>✗</span>
        </div>
        """, unsafe_allow_html=True)

# Main app function
def main():
    load_css()
    
    # App header
    st.markdown("<h1 class='main-header'>AutoCodex - Automated Review</h1>", unsafe_allow_html=True)
    
    # Sidebar for inputs
    with st.sidebar:
        st.header("Repository Settings")
        repo_name = st.text_input("GitHub Repository (format: username/repo)", placeholder="e.g., docu3C/auto-codex")
        
        max_files = st.slider("Maximum files to analyze", min_value=1, max_value=20, value=5, 
                             help="Limit the number of Java files to analyze (to avoid rate limits)")
        
        with st.expander("View Java Guidelines"):
            st.markdown(JAVA_GUIDELINES)
        
        analyze_button = st.button("Analyze Repository", type="primary")
    
    # Load API keys
    try:
        api_keys = load_api_keys()
        github_token = api_keys["github_token"]
        gemini_model = initialize_gemini(api_keys["gemini_api_key"])
    except Exception as e:
        st.error(f"Error initializing API connections: {str(e)}")
        return
    
    # Initialize session state
    if 'analysis_results' not in st.session_state:
        st.session_state.analysis_results = []
    
    # When user clicks analyze
    if analyze_button and repo_name:
        with st.spinner("Fetching Java files from the repository..."):
            java_files, error = get_java_files(repo_name, github_token)
            
            if error:
                st.error(error)
                return
            
            if not java_files:
                st.warning("No Java files found in the repository.")
                return
            
            # Limit number of files to analyze
            if len(java_files) > max_files:
                st.info(f"Repository contains {len(java_files)} Java files. Analyzing the first {max_files} files (adjust in sidebar).")
                java_files = java_files[:max_files]
            else:
                st.success(f"Found {len(java_files)} Java files in the repository.")
            
            # Create columns for file progress
            file_cols = st.columns(len(java_files))
            file_progress_placeholders = []
            
            for i, file in enumerate(java_files):
                file_name = file['path'].split('/')[-1]
                # Add filename that will remain fixed
                file_cols[i].markdown(f"<div style='text-align: center; font-size: 0.8rem;'>{file_name}</div>", unsafe_allow_html=True)
                # Create a placeholder for the progress indicator that can be updated
                file_progress_placeholders.append(file_cols[i].empty())
            
            # Main progress bar
            progress_text = st.empty()
            progress_bar = st.progress(0)
            
            # Initialize results storage
            results = []
            
            # Analyze each file
            for idx, file in enumerate(java_files):
                progress_text.text(f"Analyzing file {idx+1}/{len(java_files)}: {file['path']}")
                update_file_progress(file_progress_placeholders[idx], 30, "in_progress")

                content, error = get_file_content(repo_name, file['path'], github_token)
                analysis_success = False
                
                if not error:
                    try:
                        analysis_response = analyze_code_with_gemini(content, file['path'], gemini_model)
                        analysis_data = parse_gemini_response(analysis_response)
            
                        if analysis_data:
                            results.append({
                                "file_path": file['path'],
                                "analysis": analysis_data
                            })
                            analysis_success = True
                        else:
                            st.error(f"Failed to analyze {file['path']}")
                    except Exception as e:
                        st.error(f"Error analyzing {file['path']}: {str(e)}")
                else:
                    st.error(error)
                
                # Update progress indicator only once with final status
                update_file_progress(file_progress_placeholders[idx], 100, "success" if analysis_success else "error")
    
                # Add a small delay to avoid rate limiting
                time.sleep(0.5)
    
                # Update progress
                progress_bar.progress((idx + 1) / len(java_files))

            # Show 100% completion state before clearing
            progress_text.text(f"Analysis complete! Processed {len(java_files)} files.")
            progress_bar.progress(1.0)
            
            # Add a short pause so users can see the completed state
            time.sleep(1.5)
            
            # Save results to session state
            st.session_state.analysis_results = results
            
            # Clear progress indicators
            progress_text.empty()
            progress_bar.empty()
    
    # Display analysis results
    if st.session_state.analysis_results:
        st.markdown("<h2 class='sub-header'>Analysis Results</h2>", unsafe_allow_html=True)
        
        # Overall summary
        overall_violations = 0
        total_checks = 0
        file_count = len(st.session_state.analysis_results)
        guideline_stats = {i: {"followed": 0, "violated": 0, "unknown": 0, "mostly followed": 0} for i in range(1, 11)}
        
        for file_result in st.session_state.analysis_results:
            for guideline in file_result['analysis'].get('guidelines_analysis', []):
                guideline_num = guideline.get('guideline_number', 0)
        
                # Validate guideline number is in the expected range
                if isinstance(guideline_num, str) and guideline_num.isdigit():
                    guideline_num = int(guideline_num)
        
                # Skip if guideline number is invalid
                if guideline_num < 1 or guideline_num > 10:
                    continue
            
                status = guideline.get('status', 'unknown').lower()
                
                # Handle various status values by mapping them to the expected categories
                if status not in guideline_stats[guideline_num]:
                    if "follow" in status and "mostly" in status:
                        status = "mostly followed"
                    elif "follow" in status:
                        status = "followed"
                    elif "violat" in status:
                        status = "violated"
                    else:
                        status = "unknown"
                
                guideline_stats[guideline_num][status] += 1
                total_checks += 1
                
                if status == "violated":
                    overall_violations += 1
        
        # Calculate overall compliance rate
        overall_compliance = ((total_checks - overall_violations) / total_checks * 100) if total_checks > 0 else 0
        
        # Create summary dataframe
        summary_data = []
        for guideline_num, stats in guideline_stats.items():
            total = stats["followed"] + stats["violated"] + stats["unknown"]
            compliance_rate = (stats["followed"] / (stats["followed"] + stats["violated"]) * 100) if (stats["followed"] + stats["violated"]) > 0 else 0
            summary_data.append({
                "Guideline": f"Guideline {guideline_num}",
                "Followed": stats["followed"],
                "Violated": stats["violated"],
                "Unknown": stats["unknown"],
                "Compliance Rate": f"{compliance_rate:.1f}%"
            })
        
        summary_df = pd.DataFrame(summary_data)
        
        # Display summary statistics in cards
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div class="stats-card">
                <div class="stats-number">{file_count}</div>
                <div class="stats-label">Files Analyzed</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col2:
            st.markdown(f"""
            <div class="stats-card">
                <div class="stats-number">{total_checks}</div>
                <div class="stats-label">Guideline Checks</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col3:
            st.markdown(f"""
            <div class="stats-card">
                <div class="stats-number">{overall_violations}</div>
                <div class="stats-label">Violations Found</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col4:
            color = "#27ae60" if overall_compliance >= 80 else "#f39c12" if overall_compliance >= 50 else "#e74c3c"
            st.markdown(f"""
            <div class="stats-card">
                <div class="stats-number" style="color: {color}">{overall_compliance:.1f}%</div>
                <div class="stats-label">Overall Compliance</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Show compliance chart
        st.subheader("Guidelines Compliance Rate")
        generate_compliance_chart(summary_data)
        
        # Show summary dataframe
        st.subheader("Guidelines Compliance Details")
        st.dataframe(summary_df, use_container_width=True, hide_index=True)
        
        # Tabs for different views
        tab1, tab2, tab3 = st.tabs(["File-by-File Analysis", "Guideline Overview", "Violations Summary"])
        
        with tab1:
            # Display detailed analysis for each file
            for file_result in st.session_state.analysis_results:
                with st.expander(f"📄 {format_file_path(file_result['file_path'])}"):
                    # Display the full path inside in smaller text
                    st.caption(f"Full path: {file_result['file_path']}")
                    
                    # Display guidelines analysis
                    for guideline in file_result['analysis'].get('guidelines_analysis', []):
                        guideline_num = guideline.get('guideline_number', 'N/A')
                        description = guideline.get('guideline_description', 'N/A')
                        status = guideline.get('status', 'unknown').lower()
                        details = guideline.get('details', 'No details provided')
                        modifications = guideline.get('modifications')
                        
                        status_class = status if status in ["followed", "violated", "unknown"] else "unknown"
                        
                        st.markdown(f"<div class='guideline-header'>Guideline {guideline_num}: {description}</div>", unsafe_allow_html=True)
                        st.markdown(f"<span class='{status_class}'>Status: {status.upper()}</span>", unsafe_allow_html=True)
                        
                        st.markdown("<div class='details'>", unsafe_allow_html=True)
                        st.markdown(f"**Details:** {details}")
                        
                        if modifications and status == "violated":
                            st.markdown("<div class='modifications'>", unsafe_allow_html=True)
                            st.markdown("**Suggested Modifications:**")
                            st.code(modifications, language="java")
                            st.markdown("</div>", unsafe_allow_html=True)
                        
                        st.markdown("</div>", unsafe_allow_html=True)
                        st.markdown("---")
        
        with tab2:
            # Display analysis by guideline
            for guideline_num in range(1, 11):
                with st.expander(f"Guideline {guideline_num} - Compliance: {guideline_stats[guideline_num]['followed']}/{guideline_stats[guideline_num]['followed'] + guideline_stats[guideline_num]['violated']} files"):
                    # Find all violations for this guideline
                    violations = []
                    
                    for file_result in st.session_state.analysis_results:
                        for guideline in file_result['analysis'].get('guidelines_analysis', []):
                            if guideline.get('guideline_number') == guideline_num and guideline.get('status', '').lower() == 'violated':
                                violations.append({
                                    "file": file_result['file_path'],
                                    "details": guideline.get('details', ''),
                                    "modifications": guideline.get('modifications', '')
                                })
                    
                    if violations:
                        st.markdown(f"**Found {len(violations)} violations in {file_count} files**")
                        
                        for idx, violation in enumerate(violations):
                            st.markdown(f"**Violation #{idx+1} in {format_file_path(violation['file'])}**")
                            st.markdown(violation['details'])
                            
                            if violation['modifications']:
                                st.markdown("**Suggested fix:**")
                                st.code(violation['modifications'], language="java")
                            
                            st.markdown("---")
                    else:
                        st.markdown("No violations found for this guideline.")
        
        with tab3:
            # Compile all violations in one place
            all_violations = []
            
            for file_result in st.session_state.analysis_results:
                file_path = file_result['file_path']
                
                for guideline in file_result['analysis'].get('guidelines_analysis', []):
                    if guideline.get('status', '').lower() == 'violated':
                        all_violations.append({
                            "file": file_path,
                            "guideline": guideline.get('guideline_number', 'N/A'),
                            "description": guideline.get('guideline_description', 'N/A'),
                            "details": guideline.get('details', ''),
                            "modifications": guideline.get('modifications', '')
                        })
            
            if all_violations:
                st.markdown(f"### Found {len(all_violations)} total violations")
                
                # Create a dataframe for sorting/filtering
                violations_df = pd.DataFrame(all_violations)
                
                # Add filter
                guideline_filter = st.multiselect(
                    "Filter by Guideline", 
                    options=sorted(violations_df["guideline"].unique()),
                    default=sorted(violations_df["guideline"].unique())
                )
                
                filtered_violations = violations_df[violations_df["guideline"].isin(guideline_filter)]
                
                for _, violation in filtered_violations.iterrows():
                    with st.expander(f"Guideline {violation['guideline']} Violation in {format_file_path(violation['file'])}"):
                        st.markdown(f"**{violation['description']}**")
                        st.markdown(violation['details'])
                        
                        if violation['modifications']:
                            st.markdown("**Suggested Modification:**")
                            st.code(violation['modifications'], language="java")
            else:
                st.success("No violations found in any files!")

# Add footer
def add_footer():
    st.markdown("""
    <div style="text-align: center; margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #eee; color: #666;">
        <p>AutoCodex - docu3C</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
    add_footer()