import streamlit as st
import google.generativeai as genai
from PyPDF2 import PdfReader
from fpdf import FPDF
import time
import plotly.express as px
import pandas as pd
from dotenv import load_dotenv
import os

genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

st.set_page_config(page_title="AI Interviewer", layout="centered")

@st.cache_data
def generate_response(prompt):
    try:
        response = genai.GenerativeModel("gemini-2.0-flash").generate_content(prompt)
        return response.text.strip() if response else ""
    except Exception as e:
        st.error(f"Error with Gemini API: {e}")
        return ""


def calculate_resume_score(resume_text, job_desc):
    if not resume_text or not job_desc:
        return 0.0
    prompt = f"Evaluate the resume against the job description and provide a score (0-100).\n\nJob Description:\n{job_desc}\n\nResume:\n{resume_text}\n\nOnly provide the numeric score."
    response = generate_response(prompt)
    try:
        return float(response.split()[0])
    except ValueError:
        return 0.0


def evaluate_answer_quality(question, user_input):
    if not question or not user_input:
        return 0.0
    prompt = f"Evaluate the quality of this response on relevance, confidence, and clarity (0-100).\n\nQuestion: {question}\n\nAnswer: {user_input}\n\nProvide only the numeric score."
    response = generate_response(prompt)
    try:
        return float(response.split()[0])
    except ValueError:
        return 0.0


def provide_real_time_feedback(question, partial_answer):
    if not partial_answer:
        return "Start typing your response to receive feedback."
    prompt = f"Provide a brief, actionable suggestion to improve this partial interview response for relevance, specificity, and structure.\n\nQuestion: {question}\n\nPartial Answer: {partial_answer}"
    return generate_response(prompt)


def best_possible_answer(question):
    prompt = f"Provide the best possible answer for the following interview question:\n\nQuestion: {question}"
    return generate_response(prompt)


def provide_feedback(answers, scores):
    feedback_prompt = "Provide constructive feedback based on the candidate's answers and scores."
    for i, (answer, score) in enumerate(zip(answers, scores)):
        feedback_prompt += f"\n\nAnswer {i + 1}: {answer}\nScore: {score}/100"
    return generate_response(feedback_prompt)


def generate_interview_question(job_title, job_desc, resume_text, conversation_history, question_type="technical"):
    context = "\n".join([f"Q: {q}\nA: {a}" for q, a in conversation_history])
    if question_type == "behavioral":
        prompt = f"You are an AI interviewer for a {job_title} role. The job description is: {job_desc}.\n\nResume:\n{resume_text}\n\nPrevious conversation:\n{context}\n\nGenerate a behavioral interview question (e.g., about teamwork, conflict resolution) based on the resume, job description, and responses so far."
    else:
        prompt = f"You are an AI interviewer for a {job_title} role. The job description is: {job_desc}.\n\nResume:\n{resume_text}\n\nPrevious conversation:\n{context}\n\nAsk one relevant technical interview question based on the resume, job description, and responses so far."
    return generate_response(prompt)


def generate_content(option, resume_text, job_desc, job_title, user_name):
    prompts = {
        "LinkedIn Post": f"Generate a professional LinkedIn post for {user_name} applying for a {job_title} role. Highlight their qualifications from the resume and align with the job description. Keep it concise and engaging.\n\nResume:\n{resume_text}\n\nJob Description:\n{job_desc}",
        "LinkedIn HR Message": f"Generate a professional LinkedIn message to an HR manager for {user_name} applying for a {job_title} role. Emphasize their fit based on the resume and job description. Keep it polite and succinct.\n\nResume:\n{resume_text}\n\nJob Description:\n{job_desc}",
        "Email": f"Generate a formal job application email for {user_name} applying for a {job_title} role. Use the resume and job description to highlight qualifications. Include a subject line.\n\nResume:\n{resume_text}\n\nJob Description:\n{job_desc}",
        "Cover Letter": f"Generate a professional cover letter for {user_name} applying for a {job_title} role. Tailor it to the resume and job description, emphasizing relevant skills and enthusiasm.\n\nResume:\n{resume_text}\n\nJob Description:\n{job_desc}"
    }
    return generate_response(prompts.get(option, ""))


def generate_pdf():
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, "Interview Summary", ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("Arial", "", 12)

    def safe_text(text):
        return text.encode("latin-1", "replace").decode("latin-1") if text else ""

    pdf.cell(0, 10, f"Candidate: {safe_text(st.session_state.user_name)}", ln=True)
    pdf.cell(0, 10, f"Job Title: {safe_text(st.session_state.job_title)}", ln=True)
    pdf.cell(0, 10, f"Interview Time: {st.session_state.interview_time} minutes", ln=True)
    pdf.ln(10)

    for i, (question, answer, score) in enumerate(
            zip(st.session_state.interview_log, st.session_state.user_answers, st.session_state.answer_scores)):
        pdf.set_font("Arial", "B", 12)
        pdf.multi_cell(0, 10, f"Question {i + 1}: {safe_text(question)}")
        pdf.set_font("Arial", "", 12)
        pdf.multi_cell(0, 10, f"Answer: {safe_text(answer)}")
        pdf.cell(0, 10, f"Score: {score:.2f}/100", ln=True)
        best_answer = best_possible_answer(question)
        pdf.multi_cell(0, 10, f"Best Answer: {safe_text(best_answer)}")
        pdf.ln(5)

    avg_score = sum(st.session_state.answer_scores) / len(
        st.session_state.answer_scores) if st.session_state.answer_scores else 0
    pdf.cell(0, 10, f"Overall Interview Score: {avg_score:.2f}/100", ln=True)
    feedback = provide_feedback(st.session_state.user_answers, st.session_state.answer_scores)
    pdf.multi_cell(0, 10, f"Feedback: {safe_text(feedback)}")

    pdf.output("interview_summary.pdf", "F")
    with open("interview_summary.pdf", "rb") as f:
        st.download_button("Download Interview Summary", f, "interview_summary.pdf", key="download_summary")


def ats_analysis(job_desc, resume_text):
    prompt = f"""Perform an ATS analysis for the following job description and resume.

Job Description:
{job_desc}

Resume:
{resume_text}

Provide the analysis in the following format and only consider the major skills.:

*Matching Skills:*
- Skill 1
- Skill 2
- ...

*Missing Skills:*
- Skill 1
- Skill 2
- ...

*Suggestions:*
- Suggestion 1
- Suggestion 2
- ...
"""
    response = generate_response(prompt)
    # Parse response for visualization
    matching_skills = []
    missing_skills = []
    suggestions = []
    current_section = None
    for line in response.split("\n"):
        line = line.strip()
        if line.startswith("*Matching Skills:*"):
            current_section = "matching"
        elif line.startswith("*Missing Skills:*"):
            current_section = "missing"
        elif line.startswith("*Suggestions:*"):
            current_section = "suggestions"
        elif line.startswith("- ") and current_section:
            item = line[2:].strip()
            if current_section == "matching":
                matching_skills.append(item)
            elif current_section == "missing":
                missing_skills.append(item)
            elif current_section == "suggestions":
                suggestions.append(item)
    return response, matching_skills, missing_skills, suggestions


def generate_skill_recommendations(missing_skills):
    if not missing_skills:
        return "No missing skills identified. Focus on strengthening your existing skills!"
    prompt = f"Provide personalized learning resource recommendations (e.g., online courses, tutorials) for the following missing skills. Keep it concise and include specific platforms like Coursera, YouTube, or Udemy.\n\nMissing Skills:\n" + "\n".join(
        [f"- {skill}" for skill in missing_skills])
    return generate_response(prompt)


def visualize_ats_skills(matching_skills, missing_skills):
    # Bar chart for skill counts
    skills = matching_skills + missing_skills
    status = ["Matching"] * len(matching_skills) + ["Missing"] * len(missing_skills)
    df_bar = pd.DataFrame({"Skill": skills, "Status": status})
    fig_bar = px.bar(df_bar, x="Skill", color="Status", title="Matching vs. Missing Skills",
                     color_discrete_map={"Matching": "#00CC96", "Missing": "#EF553B"})
    fig_bar.update_layout(xaxis_tickangle=45)
    st.plotly_chart(fig_bar)

    # Radar chart for skill proficiency (hypothetical scores)
    skills = matching_skills[:5] + missing_skills[:5]  # Limit to 10 skills for clarity
    if skills:
        candidate_scores = [80 if s in matching_skills else 20 for s in skills]  # Example scores
        required_scores = [100 if s in matching_skills else 80 for s in skills]  # Job requirements
        df_radar = pd.DataFrame({
            "Skill": skills * 2,
            "Score": candidate_scores + required_scores,
            "Type": ["Candidate"] * len(skills) + ["Job Requirement"] * len(skills)
        })
        fig_radar = px.line_polar(df_radar, r="Score", theta="Skill", color="Type", line_close=True,
                                  title="Skill Proficiency Comparison")
        st.plotly_chart(fig_radar)


# Initialize session state
if 'page' not in st.session_state:
    st.session_state.update({
        'page': 1, 'resume_text': "", 'job_title': "", 'job_desc': "", 'user_name': "", 'interview_time': 10,
        'interview_log': [], 'resume_score': 0, 'answer_scores': [], 'user_answers': [], 'time_left': 600,
        'current_question': "", 'conversation_history': [], 'start_time': time.time(), 'question_type': "technical"
    })

# Page 1: Setup
if st.session_state.page == 1:
    st.title("AI Interview Setup")
    st.subheader("Candidate Information")
    st.session_state.user_name = st.text_input("Your Name", key="input_name")
    st.session_state.job_title = st.text_input("Job Title", key="input_job_title")
    st.session_state.job_desc = st.text_area("Job Description", key="input_job_desc")
    resume_file = st.file_uploader("Upload Resume (PDF)", type=["pdf"], key="resume_upload")
    st.session_state.interview_time = st.number_input("Interview Duration (minutes)", min_value=1, max_value=60,
                                                      value=10, key="input_duration")

    # Dropdown for content generation
    st.subheader("Generate Application Content")
    content_option = st.selectbox("Select Content Type",
                                  ["None", "LinkedIn Post", "LinkedIn HR Message", "Email", "Cover Letter"],
                                  key="content_select")
    if content_option != "None" and resume_file and st.session_state.job_desc:
        content = generate_content(content_option, st.session_state.resume_text, st.session_state.job_desc,
                                   st.session_state.job_title, st.session_state.user_name)
        with st.expander(f"Generated {content_option}"):
            st.markdown(content)

    # Process resume
    if resume_file:
        try:
            reader = PdfReader(resume_file)
            st.session_state.resume_text = "\n".join([page.extract_text() or "" for page in reader.pages])
        except Exception as e:
            st.error(f"Error reading PDF: {e}")

    # Single Proceed button with validation
    if st.button("Proceed", key="proceed_button"):
        if st.session_state.user_name and st.session_state.job_title and st.session_state.job_desc and st.session_state.resume_text:
            st.session_state.page = 2
            st.session_state.start_time = time.time()
            st.rerun()
        else:
            st.error("Please fill all fields and upload a resume.")

# Page 2: Resume Review
elif st.session_state.page == 2:
    st.title("Resume Review")
    st.write(f"**Candidate Name**: {st.session_state.user_name}")
    st.write(f"**Job Title**: {st.session_state.job_title}")
    st.write(f"**Job Description**: {st.session_state.job_desc}")
    st.text_area("Resume Text", st.session_state.resume_text, height=200, key="resume_display")

    if st.session_state.resume_text:
        st.session_state.resume_score = calculate_resume_score(st.session_state.resume_text, st.session_state.job_desc)
        st.write(f"**Resume Match Score**: {st.session_state.resume_score:.2f}/100")

        # ATS Analysis and Visualization
        st.subheader("ATS Analysis")
        analysis, matching_skills, missing_skills, suggestions = ats_analysis(st.session_state.job_desc,
                                                                              st.session_state.resume_text)
        st.markdown(analysis)
        visualize_ats_skills(matching_skills, missing_skills)

        # Skill Improvement Recommendations
        st.subheader("Skill Improvement Recommendations")
        recommendations = generate_skill_recommendations(missing_skills)
        st.markdown(recommendations)

        # Generate PDF for ATS analysis
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(200, 10, "ATS Analysis", ln=True, align="C")
        pdf.ln(10)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, f"Candidate: {st.session_state.user_name}", ln=True)
        pdf.cell(0, 10, f"Job Title: {st.session_state.job_title}", ln=True)
        pdf.ln(10)
        pdf.set_font("Arial", "", 12)


        def safe_text(text):
            return text.encode("latin-1", "replace").decode("latin-1") if text else ""


        pdf.multi_cell(0, 10, safe_text(analysis))
        pdf.multi_cell(0, 10, f"\nSkill Improvement Recommendations:\n{safe_text(recommendations)}")
        pdf.output("ats_analysis.pdf", "F")
        with open("ats_analysis.pdf", "rb") as f:
            st.download_button("Download ATS Analysis", f.read(), "ats_analysis.pdf", key="download_ats")

    if st.button("Proceed to Interview", key="proceed_interview"):
        st.session_state.page = 3
        st.session_state.current_question = generate_interview_question(st.session_state.job_title,
                                                                        st.session_state.job_desc,
                                                                        st.session_state.resume_text, [],
                                                                        st.session_state.question_type)
        st.rerun()

# Page 3: Interview
elif st.session_state.page == 3:
    elapsed_time = time.time() - st.session_state.start_time
    st.session_state.time_left = st.session_state.interview_time * 60 - elapsed_time

    if st.session_state.time_left <= 0:
        st.session_state.page = 4
        st.rerun()

    st.title("AI Interview")
    st.write(
        f"**Time Remaining**: {int(st.session_state.time_left // 60)} min {int(st.session_state.time_left % 60)} sec")

    # Question type toggle
    st.session_state.question_type = st.radio("Question Type", ["Technical", "Behavioral"], key="question_type_select")

    st.write(st.session_state.current_question)
    user_input = st.text_input("Your Response", key="answer_input")

    # Real-time feedback in sidebar
    st.sidebar.subheader("Real-Time Feedback")
    feedback = provide_real_time_feedback(st.session_state.current_question, user_input)
    st.sidebar.markdown(feedback)

    if st.button("Submit Answer", key="submit_answer"):
        if user_input:
            score = evaluate_answer_quality(st.session_state.current_question, user_input)
            st.session_state.answer_scores.append(score)
            st.session_state.user_answers.append(user_input)
            st.session_state.interview_log.append(st.session_state.current_question)
            st.session_state.conversation_history.append((st.session_state.current_question, user_input))
            st.session_state.current_question = generate_interview_question(st.session_state.job_title,
                                                                            st.session_state.job_desc,
                                                                            st.session_state.resume_text,
                                                                            st.session_state.conversation_history,
                                                                            st.session_state.question_type.lower())
            st.rerun()
        else:
            st.error("Please provide a response before submitting.")

# Page 4: Summary
elif st.session_state.page == 4:
    st.title("Interview Summary")
    generate_pdf()
    if st.button("Restart Interview", key="restart_interview"):
        st.session_state.page = 1
        st.rerun()
