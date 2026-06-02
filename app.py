import os
import io
import re
import json
import time

import PyPDF2
from PIL import Image
from pdf2image import convert_from_bytes

import streamlit as st
from dotenv import load_dotenv

from typing import List, Dict, Tuple, Optional, Any

# Google and Gemini SDK imports
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google_auth_oauthlib.flow import Flow

# --- Configuration and Globals ---

# Load environment variables from a .env file
load_dotenv()

# Configure the Gemini API key
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY not found. Please set it in your .env file or environment variables.")
genai.configure(api_key=api_key)

# Set the model to be used throughout the application
model_name = "gemini-2.5-flash"

# Constants for Google Drive API authentication
CLIENT_SECRETS_FILE = "client_secrets.json"
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
REDIRECT_URI = "https://hivescorer.streamlit.app/"


# Improvement suggestions based on score ranges
IMPROVEMENT_SUGGESTIONS = {
    'report': {
        'Stakeholder slide': {
            'excellent': "Outstanding stakeholder communication! Maintain this level of clarity and insight.",
            'good': "Good stakeholder slide. Consider adding more specific KPI rationale or clearer action items.",
            'average': "Basic stakeholder information present. Add primary KPI analysis, target context, and specific recommendations.",
            'poor': "Stakeholder slide needs significant improvement. Include KPI rationale, target achievement context, key highlights, challenges, and clear way forward."
        },
        'Analysis slide': {
            'excellent': "Excellent analytical depth! Your insights are comprehensive and well-supported.",
            'good': "Good analysis with solid interpretation. Consider adding more trend analysis or correlation insights.",
            'average': "Basic analysis present. Deepen your methodology, add more data interpretation, and strengthen conclusions.",
            'poor': "Analysis needs major improvement. Focus on data interpretation, trend identification, and actionable insights."
        },
        'Media plan/task plan': {
            'excellent': "Comprehensive planning! Your timeline and resource allocation are excellent.",
            'good': "Good planning structure. Consider adding more detailed risk mitigation or budget considerations.",
            'average': "Basic plan present. Add clearer timelines, resource allocation, and responsibility assignments.",
            'poor': "Planning needs significant work. Include detailed timelines, clear responsibilities, resource requirements, and deliverables."
        },
        'Innovation and Experiment': {
            'excellent': "Highly innovative approach! Your experimental thinking is impressive.",
            'good': "Good innovative elements. Consider adding more creative approaches or experimental metrics.",
            'average': "Some innovation present. Explore more creative solutions and add experimental design elements.",
            'poor': "Innovation lacking. Introduce novel approaches, creative thinking, and experimental methodologies."
        },
        'Quality of Headings and Insights': {
            'excellent': "Exceptional headings and insights! Your communication is clear and impactful.",
            'good': "Good headings and insights. Consider making them more compelling or action-oriented.",
            'average': "Basic headings present. Make them more specific, compelling, and ensure insights are actionable.",
            'poor': "Headings and insights need major improvement. Create clear, compelling headings with profound, actionable insights."
        },
        'Data Showcase': {
            'excellent': "Excellent data visualization! Your data tells a clear, compelling story.",
            'good': "Good data presentation. Consider improving chart types or data storytelling elements.",
            'average': "Basic data presentation. Improve chart clarity, data accuracy, and narrative flow.",
            'poor': "Data showcase needs significant improvement. Focus on appropriate visualizations, data quality, and clear storytelling."
        },
        'Overall Deck Presentation': {
            'excellent': "Professional, cohesive presentation! Excellent design and flow.",
            'good': "Good overall presentation. Minor formatting tweaks could enhance the professional appearance.",
            'average': "Decent presentation. Improve formatting consistency and narrative flow.",
            'poor': "Presentation quality needs major improvement. Focus on professional design, consistent formatting, and logical flow."
        }
    },
    'smm': {
        'Stakeholder slide': {
            'excellent': "Very strong summary with excellent clarity and insights.",
            'good': "Clear summary, but some KPIs or challenges could be expanded.",
            'average': "Basic summary present. Add clarity on KPIs and challenges.",
            'poor': "Slide lacks meaningful summary. Needs structure and KPI reasoning."
        },
        'Analysis slide': {
            'excellent': "Excellent analysis with rich insights and trends.",
            'good': "Good analysis. Could use more correlation with goals.",
            'average': "Basic observations, but lacks actionable insights.",
            'poor': "Poor analysis with unclear conclusions."
        },
        'Calendar for Next Month Slide': {
            'excellent': "Well-structured and strategic calendar for the next month.",
            'good': "Good structure, minor alignment gaps.",
            'average': "Basic calendar presented. Add more strategy.",
            'poor': "Slide missing clarity or full plan for next month."
        },
        'New Campaign Recommendations Slide': {
            'excellent': "Creative and relevant campaign recommendations.",
            'good': "Useful suggestions, needs stronger strategic ties.",
            'average': "Few new ideas. Needs better linkage to account goals.",
            'poor': "Weak or missing campaign recommendations."
        },
        'Quality of Headings and Insights': {
            'excellent': "Headings are clear and insights are sharp.",
            'good': "Good structure. Could improve clarity in some parts.",
            'average': "Headings or insights are too generic.",
            'poor': "Confusing or missing insights/headings."
        },
        'Data Showcase': {
            'excellent': "Excellent visual storytelling with complete data.",
            'good': "Good visuals, but some clutter or gaps.",
            'average': "Basic charts with limited interpretation.",
            'poor': "Weak data use or unclear charts."
        },
        'Creative / Campaign Showcase Slide': {
            'excellent': "Impressive creative highlights with performance context.",
            'good': "Good showcase but lacking deeper insight.",
            'average': "Some visuals present, needs context.",
            'poor': "Weak or missing creative showcase."
        },
        'Target for Next Month Slide': {
            'excellent': "Well-defined and measurable targets.",
            'good': "Clear goals. Could be more specific.",
            'average': "Basic targets with vague details.",
            'poor': "Unclear or missing goals for next month."
        },
        'Overall Deck Presentation': {
            'excellent': "Consistent, professional deck structure.",
            'good': "Neat deck, but needs better formatting.",
            'average': "Functional but inconsistent.",
            'poor': "Disjointed deck layout or branding."
        }
    },
    'email': {
        'Executive Summary in Email': {
            'excellent': "Perfectly structured email with snapshot and attachment.",
            'good': "Email is clear but snapshot could be stronger.",
            'average': "Basic email with minor structure issues.",
            'poor': "Email lacks clarity, snapshot, or structure."
        }
    },

    'qbr': {
    'Executive Summary': {
        'excellent': "Executive summary delivers sharp, structured insights—covering KPIs, challenges, and a forward-looking plan backed by data. Slides maintain a consistent visual style and layout, with strong narrative flow and professional tone. Only use if all elements are clearly and cohesively addressed.",
        'good': "Clear structure with decent insights, but may lack depth in one key area (KPI context, challenges, or future direction). Visual consistency and flow are mostly intact, though a few slides may lack polish or smooth transitions.",
        'average': "Surface-level summary that misses specificity in KPIs, actions, or learnings. Slides may appear text-heavy, visually inconsistent, or abrupt in narrative flow.",
        'poor': "Disorganized or overly generic. Lacks clarity, metrics, and actionable takeaways. Presentation suffers from poor slide layout, inconsistent design, and weak storytelling."
    },
    'Brand Performance': {
        'excellent': "Comprehensive, data-rich brand performance analysis with strong linkage to creative, category, and audience learnings. Slides are visually polished with a good balance of text and visuals, maintaining alignment and design consistency throughout.",
        'good': "Addresses key areas but may lack depth or linkage to outcomes. Most slides are well-designed, but some may have text-heavy blocks or inconsistent alignment.",
        'average': "Basic metrics presented with limited insights. Design aesthetic may be underdeveloped—e.g., imbalanced text-to-visual ratio or inconsistent visual elements.",
        'poor': "Metrics are shown without context or strategic insight. Slide layout and visual execution are disjointed, reducing clarity and impact."
    },
    'Competitor Analysis': {
        'excellent': "In-depth, multi-angle competitor analysis using tools, creative audits, influencer tracking, and product launches. Slides follow a clear structure with consistent tone, grammar, and visual formatting to support easy comparison.",
        'good': "Covers some areas with value but lacks full coverage or clear takeaways. Presentation may include some inconsistencies in layout, visual styling, or tone.",
        'average': "High-level mentions without deep comparison or analysis. Visual and narrative structure feels generic or uneven.",
        'poor': "Minimal or unclear competitive intelligence. Lacks formatting consistency, narrative logic, and visual clarity."
    },
    'Strategy and Growth and Efficiency': {
        'excellent': "A sharp, data-supported plan with clear KPIs, publisher/channel-level tactics, risks, and projected gains. Visual narrative is cohesive with clean transitions, consistent layout, and effective text-visual balance. Grammar and tone are precise and aligned with the audience.",
        'good': "Good structure and direction, but lacks detail in areas like risk, channel planning, or expected outcomes. Visuals and narrative mostly flow well but may need minor refinement.",
        'average': "Strategy exists but feels too vague or high-level. Slide transitions may be abrupt, and the layout or storytelling lacks polish.",
        'poor': "Strategy is unclear or absent. Slides lack logical flow, contain text-heavy or poorly designed visuals, and disrupt engagement."
    },
    'Client Buy-Ins (Bonus Section)': {
        'excellent': "New initiatives are well-rationalized and supported with compelling, relevant case studies. Connection to client objectives is clear, and slides are grammatically sound, visually consistent, and structured to support persuasive storytelling.",
        'good': "Some initiatives shown with loosely connected case references. Grammar, tone, or visual alignment may need minor improvements. Avoid this unless rationale and flow are reasonably clear.",
        'average': "Mentions initiatives but lacks strong backing or linkage. Slides may be cluttered or text-dense, with weak transitions or visual inconsistency.",
        'poor': "No visible buy-ins or initiative documentation. Section lacks logic, coherence, and presentation quality—grammar and visuals undermine clarity."
    }
}

}

def get_improvement_suggestion(parameter, score, max_score, doc_type):
    """Get improvement suggestion based on parameter, score, and document type"""
    if doc_type not in IMPROVEMENT_SUGGESTIONS:
        return "Continue to focus on quality and best practices."
    
    if parameter not in IMPROVEMENT_SUGGESTIONS[doc_type]:
        return "Continue to focus on quality and best practices."
    
    percentage = (score / max_score) * 100
    suggestions = IMPROVEMENT_SUGGESTIONS[doc_type][parameter]
    
    if percentage >= 85:
        return suggestions['excellent']
    elif percentage >= 70:
        return suggestions['good']
    elif percentage >= 50:
        return suggestions['average']
    else:
        return suggestions['poor']

# Improved prompt templates with clearer instructions

PROMPT_TEMPLATE_REPORT = """
You are an expert evaluator. Carefully review the uploaded PDF deck and score it by following this exact rubric word by word.  
The purpose is to ensure consistency: you must assign scores **strictly according to the rules below**.  
If content is missing, unclear, or in wrong format → award the lowest possible score as defined.

General Rules:
- Only assign full marks if EVERY requirement is explicitly present and correct.  
- If only partial evidence is found → give proportionally low marks as per scoring guide.  
- If table-only content is provided instead of summary, penalize severely.  
- Never assume intent or infer missing information.  
- Always choose the LOWER score if uncertain.  
- Write short, factual justifications (no praise words).  
- If the slide contains everything from the "reference sheet" → award full marks immediately.  
- If only "Target vs Achieved" as a table is present → assign the lowest bracket score.  
- If experiments are mentioned → check carefully word by word for Problem Statement, Hypothesis, Learnings, and Supporting Data.
- Assign proper points according to the scoring guide.

-------------------------------------------------------
OUTPUT FORMAT (must follow exactly):
Stakeholder slide: [score out of 20] | [justification]
Analysis slide: [score out of 15] | [justification]
Media plan/task plan: [score out of 10] | [justification]
Innovation and Experiment: [score out of 10] | [justification]
Quality of Headings and Insights: [score out of 10] | [justification]
Data Showcase: [score out of 10] | [justification]
Overall Deck Presentation: [score out of 5] | [justification]
-------------------------------------------------------

SCORING CRITERIA (Strict Human-Like Rubric)
===========================================

1. Stakeholder Slide (20 points)

Required Components:  
- Primary KPI clearly stated and rationale for its growth or decline explained (5 pts)  
- Target achieved or missed stated with supporting context (5 pts)  
- Key highlights of account or campaign performance summarized (5 pts)  
- Challenges faced identified, along with concrete recommendations (3 pts)  
- Clear and actionable way forward provided (2 pts)  

Scoring Guide:  
- If slide contains only a “Target vs Achieved” table without any narrative or highlights → 2 points  
- If only raw numbers or final metric provided with no rationale, highlights, or insights → 1 point  
- If highlights and KPI included but challenges or way forward missing or vague → 5 to 10 points based on extent of missing elements  
- If no KPI or targets mentioned at all → 0 points  
- If stakeholder slide contains nothing but tables with no insights, experiments, challenges, or targets → 0 to 3 points  
- If every element above is present with clear, concise bullet points or sentences (no excessive tables) → 20 points  

Evaluation focus: The slide must read as an executive summary conveying key information succinctly with explanation—not as raw data presentation.

**Analysis slide (max 15):**
- Evaluate the Analysis slide using the criteria below. The slide should reflect a clear understanding of performance trends through account- or industry-specific insights. It must identify the root cause of growth or loss and suggest informed next steps.
- Score the slide out of 15 points based on the presence and quality of the following elements:
--Clear and relevant title (1 point)
--Strong supporting data that illustrates the analysis (7 points)
--Insightful and actionable future actions based on the analysis (7 points)

Evaluation focus: The analysis slide must demonstrate understanding of performance drivers, root causes, and include well-founded recommendations or next steps, not just data visualization.

---

General penalty note for both slides:  
If content is ambiguous, incomplete, or partially meets a criterion, always assign the lower end of the applicable score range. Strict adherence to presence and clarity of each component is essential.


3. Media Plan / Task Plan (10 points)
--------------------------------------
Required Components:
• Clear measurable targets (3 pts)  
• Strategy/tasks to achieve targets (5 pts)  
• Link to detailed plan/task sheet (2 pts)  

Scoring Guide:
• Only “Target vs Achieved” table → 1–3 pts.  
• Targets mentioned but no clear actionable tasks → 4–6 pts.  
• Well documented targets and strategies but missing links → 7–8 pts.  
• Fully detailed plan with strategy and working link → 9–10 pts.

4. Innovation & Experiment (10 points)
---------------------------------------
Required Components:
• Problem statement (2 pts)  
• Hypothesis/rationale (2 pts)  
• Key learnings (3 pts)  
• Supporting data validating/challenging learnings (3 pts)  

Scoring Guide:
• Absent (no experiment info) → 0.  
• Generic or high-level mention, no structure → 1–4 pts.  
• Some structure with partial coverage (2 of 4 elements) → 5–6 pts.  
• Full structure with hypothesis, learnings, and some data → 7–8 pts.  
• All elements complete with data-backed insights → 9–10 pts.

5. Quality of Headings & Insights (10 points)
---------------------------------------------
Required Components:
• Clear, relevant headings (5 pts)  
• Actionable insights for each chart/table/visual (5 pts)  

Scoring Guide:
• Only tables with headings but no insights → 1–3 pts.  
• Clear structure but insights missing in many areas → 4–6 pts.  
• Headings + partial insights but inconsistent → 6–7 pts.  
• Strong, well-labeled slides with consistent insights → 8–10 pts.

6. Data Showcase (10 points)
-----------------------------
Scoring Guide:
• 9–10: All relevant data by channel/category shown with appropriate visuals. No major gaps.  
• 7–8: Good data with minor visualization/clarity issues.  
• 5–6: Basic tables/charts but lacks completeness or clarity.  
• 2–4: Very poor quality visuals/tables, data incomplete.  
• 0–1: No meaningful data shown.

7. Overall Deck Presentation (5 points)
----------------------------------------
Required Components:
• Consistent font, layout, and formatting (2 pts)  
• Updated logos on all slides (2 pts)  
• Latest closing/Thank You slide (1 pt)  

Scoring Guide:
• Missing logos/branding elements or inconsistent formatting → 1–3 pts.  
• Mostly consistent, but branding not updated everywhere → 4 pts.  
• Fully updated, consistent, professional → 5 pts.
"""



PROMPT_TEMPLATE_SMM_REPORT = """
You are an expert evaluator. Carefully analyze the uploaded PDF document and score it according to the exact criteria described below.

Your output MUST follow these rules:

- Be highly critical and unbiased. Review each section like a senior stakeholder would. Do NOT inflate scores under any circumstance.
- Strictly follow the scoring rubric. Give full marks ONLY when every criterion is clearly and completely fulfilled with strong evidence.
- Penalize missing, vague, generic, or visually unclear content. If a part is weak or partially met, assign proportionally low scores.
- If you are unsure about the quality or presence of a component, assign the **lower** score. Never assume or infer intent.
- Use professional language. Be brief, direct, and specific in justifications. No praise or filler words.

IMPORTANT: Return ONLY the scores and justifications in this exact format,Return ALL of the below parameters even if the content is missing. If a slide is not found, give it a score of 0 and say "Slide not found".
:
Stakeholder slide: [score] | [brief justification explaining why this score was given]
Analysis slide: [score] | [brief justification explaining why this score was given]
Calendar for Next Month Slide: [score] | [brief justification explaining why this score was given]
New Campaign Recommendations Slide: [score] | [brief justification explaining why this score was given]
Quality of Headings and Insights: [score] | [brief justification explaining why this score was given]
Data Showcase: [score] | [brief justification explaining why this score was given]
Creative / Campaign Showcase Slide: [score] | [brief justification explaining why this score was given]
Target for Next Month Slide: [score] | [brief justification explaining why this score was given]
Overall Deck Presentation: [score] | [brief justification explaining why this score was given]



SCORING CRITERIA:
**Stakeholder slide (max 20):**
-Evaluate the Stakeholder slide using the criteria below. The slide should be an executive summary, not a data table. It must communicate key information effectively to decision-makers.
-Score the slide out of 20 points based on the presence and quality of the following elements:
--Primary KPI and a clear rationale for its growth or decline (5 points)
--Target achieved or missed, with context (5 points)
--Key highlights in account performance (5 points)
--Challenges faced and recommendations provided (3 points)
--Clear and actionable way forward (2 points)

**Analysis slide (max 15):**
- Evaluate the Analysis slide using the criteria below. The slide should reflect a clear understanding of performance trends through account- or industry-specific insights. It must identify the root cause of growth or loss and suggest informed next steps.
- Score the slide out of 15 points based on the presence and quality of the following elements:
--Clear and relevant title (1 point)
--Strong supporting data that illustrates the analysis (7 points)
--Insightful and actionable future actions based on the analysis (7 points)

**Calendar for Next Month Slide (Max 10 Points):**
- Evaluate the slide for completeness and clarity in representing upcoming social media activities. The calendar should reflect the planned content, strategies, and timelines for the next month.
- Score the slide out of 10 points based on the following criteria:
--Clear and well-structured calendar showcasing upcoming SMM activities and campaigns (5 points)
--Inclusion of strategic objectives or themes for the planned content (3 points)
--Alignment of calendar with broader monthly goals or media plan (2 points)

**New Campaign Recommendations Slide (Max 10 Points):**
- Evaluate the slide for the quality and strategic value of suggested new campaigns. This slide should present innovative or experimental ideas tailored to the account's growth and engagement objectives.
- Score the slide out of 10 points based on the following criteria:
--Relevance and originality of recommended campaigns (4 points)
--Clear explanation of the objective and expected outcome for each recommendation (3 points)
--Alignment with account goals and current performance insights (3 points)

**Quality of Headings and Insights (max 10):**
-Evaluate the clarity and effectiveness of headings and insights across the slide. Each slide should guide the viewer through structured information with clear labels and meaningful takeaways.
-Score the slide out of 10 points based on the presence and quality of the following elements:
--Clear, relevant headings for each section or topic (5 points)
--Actionable insights provided for every data point, chart, or visual presented (5 points)

**Data Showcase (max 10):**
- 9-10: All the relevant data specific to every channel or category should to be present in the deck.
- 7-8: Good data presentation with mostly appropriate visualizations. Data supports the narrative well. Minor presentation issues.
- 5-6: Basic data presentation but charts may be unclear or inappropriate for the data type. Some data quality issues.
- 2-4: Poor data visualization. Charts are confusing or misleading. Data quality concerns.
- 0-1: Very poor or missing data showcase. No clear data story or severely flawed presentation.

**Creative / Campaign Showcase Slide (Max 5 Points):**
-Evaluate the slide for the presentation and performance of key creative assets or campaigns. It should effectively highlight the visual execution and its impact.
-Score the slide out of 5 points based on the following criteria:
--Display of key creatives or campaign visuals relevant to the account (2 points)
--Brief context or objective behind the showcased content (1 point)
--Performance metrics or impact results associated with the campaigns (2 points)

**Target for Next Month Slide (Max 5 Points):**
-Evaluate the slide for clarity and relevance of the upcoming month's goals. The targets should be specific, measurable, and aligned with the account’s overall strategy.
-Score the slide out of 5 points based on the following criteria:
--Clearly defined targets for the upcoming month (2 points)
--Targets are specific, measurable, and relevant to SMM goals (2 points)
--Alignment with past performance and strategic direction (1 point)

**Overall Deck Presentation (max 5):**
-Evaluate the consistency and completeness of the overall presentation deck. The deck should maintain visual uniformity and include all standard branding and closing elements.
-Score the deck out of 5 points based on the following criteria:
--Consistent font, layout, and formatting across all slides (2 points)
--Updated client and HM logos present on all slides (2 points)
--Latest ‘Thank You’ slide included at the end (1 point)
"""
PROMPT_TEMPLATE_EMAIL = """
You are an expert evaluator. Carefully analyze the uploaded PDF document and score it according to the exact criteria described below.

Your output MUST follow these rules:

- Be highly critical and unbiased. Review each section like a senior stakeholder would. Do NOT inflate scores under any circumstance.
- Strictly follow the scoring rubric. Give full marks ONLY when every criterion is clearly and completely fulfilled with strong evidence.
- Penalize missing, vague, generic, or visually unclear content. If a part is weak or partially met, assign proportionally low scores.
- If you are unsure about the quality or presence of a component, assign the **lower** score. Never assume or infer intent.
- Use professional language. Be brief, direct, and specific in justifications. No praise or filler words.

IMPORTANT: Return ONLY the scores and justifications in this exact format.Return ALL of the below parameters even if the content is missing. If a slide is not found, give it a score of 0 and say "Slide not found".
:
Executive Summary in Email: [score] | [brief justification explaining why this score was given]

**Executive Summary in Email (Max 10 Points):**
-Evaluate the quality and completeness of the monthly report email shared with the client. The email should be professional, informative, and easy to understand at a glance.
-Score the email out of 10 points based on the following criteria:
--Properly formatted subject line: [Agency Name] | [Client Name] | [Account Type] | [Report Type] | [Report Month] | [Platform (optional)] (2 points)
--Clear snapshot of key performance metrics (3 points)
--Actionable insights on performance trends (3 points)
--Monthly report deck attached as an offline file (2 points)
"""

PROMPT_TEMPLATE_QBR = """
You are an expert evaluator. Carefully analyze the uploaded PDF document and score it according to the exact criteria described below.

Note : If you find anything which is related to what the prompts given to you then give full scores.

Check follwing paramters in slides if not mention in suggestion :
- Evaluate whether all slides maintain a consistent visual style, layout structure, and alignment in line with professional presentation standards.
- Assess the balance between text and visuals on each slide to ensure information is conveyed clearly without overwhelming the viewer with too much text.
- Evaluate the overall visual appeal of the presentation, including color harmony, typography, spacing, and graphic style consistency to ensure a polished and professional look.
- Assess the presentation for correct grammar, punctuation, and consistency in tone to ensure clarity, professionalism, and alignment with the intended audience.
- Assess whether the presentation follows a clear and structured storyline that guides the client logically from the problem or objective, through insights and strategies, to conclusions or next steps. Check if each slide transitions smoothly into the next, building on the previous content without abrupt jumps. Ensure the narrative answers key client questions and maintains engagement throughout. The flow should support persuasive storytelling tailored to the client’s context.

IMPORTANT: Return ONLY the scores and justifications in this exact format. Return ALL of the below parameters even if the content is missing. If a slide is not found, give it a score of 0 and say "Slide not found".

:
Executive Summary: [score] | [brief justification explaining why this score was given]
Brand Performance: [score] | [brief justification explaining why this score was given]
Competitor Analysis: [score] | [brief justification explaining why this score was given]
Strategy and Growth and Efficiency: [score] | [brief justification explaining why this score was given]
Client Buy-Ins (Bonus Section): [score] | [brief justification explaining why this score was given]

SCORING CRITERIA:

**Executive Summary (max 22):** 
- Evaluate the Executive Summary using the criteria below. The section should provide a concise overview of the quarter's performance, key takeaways, and future outlook, with a mandatory focus on innovation.
- Score the section out of **20 points** based on the presence and quality of the following elements:
    -- **Slide focusing on Major Wins, Key Achievements, Major Highlights, Awards, New Initiatives, summarizing key highlights.** (3 points) 
    -- **Details regarding the initiatives planned in the previous meeting along with the current implementation status. In case not implemented, the challenges, blocker or rationale should be mentioned.** (4 points) 
    -- **1 slider that build the overall context of what the client can look forward to in the meeting. Also, this should have atleast 2-3 innovative, delightful or outshine initiatives being suggested** (4 points) 
    -- **QoQ Performance Overview** (3 points) 
    -- **Key Analysis with Objective and Result** (3 points) 
    -- **New Experiments/Initiatives** (Existing or New Channels) (3 points) 
    -- **Section Summary, Key Takeaways, Major Pointers, Key Learnings that clearly help the client know the final focus areas from a particular section.** (2 points) 

**Brand Performance (max 15):** 
- Evaluate the Brand Performance section using the criteria below. This section should detail the performance across various channels and provide insights into creative, category, product, and audience performance.
- Score the section out of **15 points** based on the presence and quality of the following elements:
    -- **Performance view with insights on what worked, challenges faced and plan ahead (if required)** (4 points) 
    -- **Visual insights on creatives that performed and the ones which did not deliver. Highlight communication angles that worked well.** (3 points) 
    -- **Highlight the top performing categories for the brand with insights into noticeable trends if any.** (3 points) 
    -- **Audience trends, top performing cohorts** (3 points) 
    -- **Section Summary, Key Takeaways, Major Pointers, Key Learnings that clearly help the client know the final focus areas from a particular section.** (2 point) 

**Competitor Analysis (max 13):** 
- Evaluate the Competitor Analysis section using the criteria below. This section should offer insights derived from competitor intelligence tools, covering creative, marketing initiatives, new product innovation, and collaborations.
- Score the section out of **13 points** based on the presence and quality of the following elements:
    -- **Tool Insights** - Similar Web, App Annie, Sensor Tower (2 points) 
    -- **Compare the creative strategy by analysing multiple sources like Ads Library, Ads Transparency, Social channels etc to judge the creative parameters that distinguish competitor assets.** (2 points) 
    -- **Highlight the innovative marketing initiatives taken by the competitor which caused a positive buzz and can be replicated** (2 points) 
    -- **Identify the new markets/products/customers that the competitors are venturing in, to stay ahead of the curve** (3 points) 
    -- **Mention the celeb/influencer collaboration with teh use case.** (2 point) 
    -- **Section Summary, Key Takeaways, Major Pointers, Key Learnings that clearly help the client know the final focus areas from a particular section.** (2 point) 

**Strategy and Growth and Efficiency (max 40):** 
- Evaluate the Strategy: Growth & Efficiency section using the criteria below. This crucial section should outline the strategic plan, objectives, initiatives, proposed returns, channel-level strategies, experiments, media innovations, and publisher plans.
- Score the section out of **40 points** based on the presence and quality of the following elements:
    -- **Clear mention of the core goals/objectives for the upcoming quarter along with the rationale behind them and the KPI that can be tracked to measure the result.** (10 points) 
    -- **Media outlook with proposed returns** (Phasing, if required) (6 points) 
    -- **Channel Level Strategy** (6 points) 
    -- **New experiments for improvements that can either be based out of channel learnings/analysis or on the beta cards shared by Google and Meta teams.** (6 points) 
    -- **Media Innovations (Impact Property/New Tool/Industry Insight etc) - an outshining insight** (6 points) 
    -- **Publisher Plans - New channels unlocks with purpose, selection rationale and KPI** (6 points) 

**Client Buy-Ins (Bonus Section) (max 10):** 
- Evaluate the Client Buy-Ins (Bonus Section) section using the criteria below. This section should present Hivemind Case Studies, details on Client Buy-Ins (Bonus Section), and new initiatives that require client approval or partnership.
- Score the section out of **10 points** based on the presence and quality of the following elements:
    -- **Organization Case Studies** (5 points)  
    -- **AI Experiments/Initiatives and New Initiatives** (5 points) 
    
"""

# Score definitions
max_scores_report = {
    'Stakeholder slide': 20,
    'Analysis slide': 15,
    'Media plan/task plan': 10,
    'Innovation and Experiment': 10,
    'Quality of Headings and Insights': 10,
    'Data Showcase': 10,
    'Overall Deck Presentation': 5
}

max_scores_smm_report = {
    'Stakeholder slide': 20,
    'Analysis slide': 15,
    'Calendar for Next Month Slide': 10,
    'New Campaign recommendations Slide': 10,
    'Quality of Headings and Insights': 10,
    'Data Showcase': 10,
    'Creative / Campaign Showcase Slide': 5,
    'Target for Next Month Slide': 5,
    'Overall Deck Presentation': 5
}

max_scores_email = {
    'Executive Summary in Email': 10
}

max_scores_qbr = {
    'Executive Summary':22,
    'Brand Performance':15,
    'Competitor Analysis':13,
    'Strategy and Growth and Efficiency':40,
    'Client Buy-Ins (Bonus Section)':10

}


# Critical score logic per report type
CRITICAL_SCORING_RULES = {
    'report': [
        {
            'parameter': 'Stakeholder slide',
            'missing_phrase': 'Target achieved or missed',
            'deduction': 5,
            'reason': 'Target achievement context is missing in the stakeholder slide.',
            'suggestion': 'Include whether the target was achieved or missed along with clear context or rationale.'
        }
    ],
    'smm': [
        {
            'parameter': 'Stakeholder slide',
            'missing_phrase': 'Target achieved or missed',
            'deduction': 5,
            'reason': 'Target achievement context is missing in the stakeholder slide.',
            'suggestion': 'Add a statement on whether targets were achieved or missed, including a contextual explanation.'
        }
    ],
    'email': [
        {
            'parameter': 'Executive Summary in Email',
            'missing_phrase': 'snapshot of key performance metrics',
            'deduction': 3,
            'reason': 'Snapshot of key performance metrics is missing in the executive summary.',
            'suggestion': 'Add a clear snapshot summarizing key performance metrics for the reporting period.'
        }
    ],
    'qbr': [
        {
            'parameter': 'Executive Summary',
            'missing_phrase': 'implementation status',
            'deduction': 1,
            'reason': 'Implementation status and challenges of past initiatives are missing.',
            'suggestion': 'Include details of previous initiatives and update their implementation status or challenges.'
        },
        {
            'parameter': 'Executive Summary',
            'missing_phrase': 'context of what the client can look forward to',
            'deduction': 1,
            'reason': 'Forward-looking initiatives and client context are missing.',
            'suggestion': 'Add a context-setting slide for upcoming quarter with 2–3 new or outshining initiatives.'
        },
        {
            'parameter': 'Strategy and Growth and Efficiency',
            'missing_phrase': 'core goals/objectives for the upcoming quarter',
            'deduction': 1,
            'reason': 'Clear goals and KPIs for next quarter are missing.',
            'suggestion': 'Clearly mention core goals/objectives, rationale, and KPIs to track for the next quarter.'
        }
    ]
}



CLIENT_SECRETS_FILE = "client_secrets.json"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
REDIRECT_URI = "http://localhost:8501/"

@st.cache_resource
def get_google_auth_flow():
    if not os.path.exists(CLIENT_SECRETS_FILE):
        st.error(f"`{CLIENT_SECRETS_FILE}` not found. Please follow prerequisites.")
        st.stop()
    return Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI)

def build_drive_service() -> Optional[Any]:
    creds_data = st.session_state.get("google_creds")
    if not creds_data:
        return None
    creds = Credentials.from_authorized_user_info(creds_data, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        st.session_state.google_creds = json.loads(creds.to_json())
    return build('drive', 'v3', credentials=creds)

def list_drive_pdfs(service: Any) -> List[Dict[str, str]]:
    try:
        results = service.files().list(q="mimeType='application/pdf' and trashed=false", pageSize=200, fields="files(id, name)").execute()
        return results.get('files', [])
    except Exception as e:
        st.error(f"Failed to list Google Drive files: {e}")
        return []

def get_drive_files_in_memory(service: Any, files: List[Dict]) -> List[Tuple[str, io.BytesIO]]:
    in_memory_files = []
    progress_bar = st.progress(0, text="Starting download from Google Drive...")
    for i, file_info in enumerate(files):
        progress_text = f"Downloading {file_info['name']} ({i+1}/{len(files)})..."
        progress_bar.progress((i + 1) / len(files), text=progress_text)
        request = service.files().get_media(fileId=file_info['id'])
        file_buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(file_buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        file_buffer.seek(0)
        in_memory_files.append((file_info['name'], file_buffer))
    progress_bar.empty()
    return in_memory_files

# Enhance parse_scores to apply critical score
def extract_text_from_pdf(uploaded_pdf):
    reader = PyPDF2.PdfReader(uploaded_pdf)
    text = "\n".join([page.extract_text() or "" for page in reader.pages])
    return text


def generate_gemini_response(prompt, context):
    model = genai.GenerativeModel("gemini-2.5-flash")
    chat = model.start_chat(history=[])
    response = chat.send_message(f"{context}\n\nUser: {prompt}")
    return response.text

import re

import re
import streamlit as st

def apply_critical_deductions(parameter, justification, doc_type, critical_rules):
    """
    Checks the justification against a set of rules and returns the total deduction.
    """
    total_deduction = 0
    # Get the list of rules for the current document type (e.g., 'qbr')
    rules_for_doctype = critical_rules.get(doc_type, [])

    for rule in rules_for_doctype:
        # Check if the rule is for the correct parameter
        if rule.get('parameter') == parameter:
            # Check if the justification contains the specific phrase that triggers a deduction
            # The search is case-insensitive to make it more reliable
            if rule.get('missing_phrase', '').lower() in justification.lower():
                total_deduction += rule.get('deduction', 0)
                
    return total_deduction


def parsescores(response_text, max_scores, doc_type):
    """
    Final, robust parser to extract all parameters from the Gemini response,
    even with variable spacing.
    """
    scores = []
    
    # This regex is more flexible. It identifies the start of a new parameter
    # based on its unique "Name: Score | Justification" structure, regardless of newlines.
    pattern = re.compile(
        r"^(?P<parameter>[\w\s\(\)-]+?):\s*(?P<score>\d+)\s*\|\s*(?P<justification>[\s\S]+?)(?=\n[A-Z][\w\s\(\)-]*:\s*\d+\s*\||\Z)",
        re.MULTILINE
    )

    for match in pattern.finditer(response_text):
        parameter = match.group('parameter').strip()
        score_str = match.group('score').strip()
        justification = match.group('justification').strip()

        max_score = max_scores.get(parameter)

        if max_score is not None and score_str.isdigit():
            score = int(score_str)
            percentage = (score / max_score * 100) if max_score > 0 else 0
            
            improvement_suggestion = get_improvement_suggestion(parameter, score, max_score, doc_type)

            scores.append({
                'Parameter': parameter,
                'Score': score,
                'Max Score': max_score,
                'Critical Score': 0,
                'Percentage': f"{percentage:.1f}%",
                'Score Justification': justification,
                'Improvement Suggestions': improvement_suggestion
            })
    
    if not scores:
        st.error("Could not parse any scores from the Gemini response. Check the raw response format.")
        
    return scores



# Upload PDF to Gemini
import streamlit as st
import google.generativeai as genai

def upload_pdf_to_gemini(uploaded_file):
    """
    Uploads a PDF file from a file-like object (e.g., Streamlit's UploadedFile)
    to Gemini and returns a file handle.
    """
    st.info("Uploading PDF to Gemini...")
    try:
        # Pass the file-like object to 'path' and specify the mime_type
        gemini_file = genai.upload_file(
            path=uploaded_file,
            display_name=uploaded_file.name,
            mime_type="application/pdf"  # Add this line
        )
        st.success("PDF uploaded successfully.")
        return gemini_file
    except Exception as e:
        st.error(f"Error uploading PDF to Gemini: {e}")
        return None

    

def get_scores_from_gemini_pdf(gemini_file, prompt_template, max_scores, doc_type):
    """
    Generates content from an uploaded file, displays the raw response for debugging,
    and then parses the scores.
    """
    if not gemini_file:
        st.error("File upload failed, cannot get scores.")
        return None

    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        st.info("Getting evaluation from Gemini...")
        response = model.generate_content([prompt_template, gemini_file])

        if not response.text:
            st.error("No response received from Gemini API.")
            return None
            
        # --- DEBUGGING STEP ---
        # This will create a text box in your app showing the exact output from the AI.
        st.text_area("Raw Response from Gemini API", response.text, height=250)
        
        # The parsing function is called after displaying the raw text.
        scores = parsescores(response.text, max_scores, doc_type)
        return scores
        
    except Exception as e:
        st.error(f"An error occurred while getting scores from Gemini: {e}")
        return None
    finally:
        if gemini_file:
            st.info("Deleting uploaded file...")
            genai.delete_file(gemini_file.name)
            st.success("File deleted.")



# Function to display results
def display_results(scores, title, doc_type):
    st.subheader(f"📊 {title} Evaluation Results")

    if scores:
        df = st.dataframe(
            scores,
            use_container_width=True,
            column_config={
                "Parameter": st.column_config.TextColumn("Parameter", width="medium"),
                "Critical Score": st.column_config.NumberColumn("Critical Score", width="small"),
                "Score": st.column_config.NumberColumn("Score", width="small"),
                "Max Score": st.column_config.NumberColumn("Max Score", width="small"),
                "Percentage": st.column_config.TextColumn("Percentage", width="small"),
                "Score Justification": st.column_config.TextColumn("Score Justification", width="large"),
                "Improvement Suggestions": st.column_config.TextColumn("Improvement Suggestions", width="large")
            }
        )

        total_score = sum(item['Score'] for item in scores if isinstance(item['Score'], (int, float)))
        total_possible = sum(item['Max Score'] for item in scores if isinstance(item['Max Score'], (int, float)))
        total_critical = sum(item['Critical Score'] for item in scores if isinstance(item['Critical Score'], (int, float)))

        percentage = (total_score / total_possible) * 100 if total_possible > 0 else 0

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Score", f"{total_score}/{total_possible}")
        with col2:
            st.metric("Critical Deductions", f"{total_critical}")
        with col3:
            st.metric("Percentage", f"{percentage:.1f}%")
        with col4:
            if percentage >= 80:
                st.success("🎉 Excellent!")
            elif percentage >= 60:
                st.warning("👍 Good")
            else:
                st.error("📈 Needs Improvement")

        st.progress(percentage / 100)

        return percentage
    else:
        st.error("No scores to display")
        return 0

# --- Streamlit UI for Uploads with Google Drive Option ---
st.set_page_config(page_title="Quality Assurance Check", layout="wide")
st.title("📊 Quality Assurance Check")
# Instructions (update the text to include QBR)
with st.expander("ℹ️ How to use this tool"):
    st.write("""
    1. **Upload only one PDF** at a time (Monthly Report, Email, SMM Report, or QBR).
    2. Wait for the file to process and results to generate.
    3. Review the AI-evaluated scores and improvement suggestions.
    **What this tool does:**
    - ✅ AI-based scoring of reports
    - ✅ Personalized improvement suggestions
    - ✅ Gemini 2.5 Flash used for analysis
    """)
st.write("Upload **only one** of the following: Monthly Report, SMM Report, Email, or QBR PDF for evaluation")
with st.expander("🔑 Connect your Google Drive (required for Drive uploads)", expanded=False):
    if "google_creds" not in st.session_state:
        if st.button("🔗 Authorize Google Drive"):
            flow = get_google_auth_flow()
            auth_url, _ = flow.authorization_url(prompt="consent")
            st.markdown(f"[Click here to authorize]({auth_url})")
            st.session_state.auth_flow = flow

        # Handle token return after auth
        query_params = st.query_params if hasattr(st, 'query_params') else st.experimental_get_query_params()
        if "code" in query_params and "auth_flow" in st.session_state:
            try:
                flow = st.session_state.auth_flow
                flow.fetch_token(code=query_params["code"])
                creds = flow.credentials
                st.session_state.google_creds = json.loads(creds.to_json())
                st.success("✅ Google Drive access granted.")
                del st.session_state["auth_flow"]
            except Exception as e:
                st.error(f"Failed to complete authorization: {e}")
    else:
        st.success("✅ Google Drive is already connected.")


col1, col2, col3, col4 = st.columns(4)

# Helper function to display Drive upload option
def handle_drive_upload(label_key):
    if "google_creds" in st.session_state:
        service = build_drive_service()
        drive_files = list_drive_pdfs(service)
        if drive_files:
            selected = st.selectbox(f"Select from Drive - {label_key}", [f["name"] for f in drive_files], key=f"{label_key}_select")
            selected_file = next(f for f in drive_files if f["name"] == selected)
            file_name, file_buffer = get_drive_files_in_memory(service, [selected_file])[0]
            file_buffer.name = file_name
            file_buffer.type = "application/pdf"
            return file_buffer
    return None

with col1:
    st.subheader("📈 Monthly Report")
    uploaded_report = st.file_uploader("Upload Monthly Report (PDF)", type="pdf", key="report")

    if st.button("📂 From Drive (Monthly)", key="drive_monthly_btn"):
        st.session_state.drive_mode = "monthly"

    if st.session_state.get("drive_mode") == "monthly":
        if "google_creds" not in st.session_state:
            st.warning("Please authorize Google Drive access using the expander above.")
        else:
            drive_service = build_drive_service()
            drive_files = list_drive_pdfs(drive_service)
            if drive_files:
                selected_file_name = st.selectbox("Select Monthly Report from Drive", [f["name"] for f in drive_files], key="monthly_drive_file")
                if st.button("✅ Use Selected Monthly Report from Drive", key="use_drive_monthly"):
                    selected_file = next((f for f in drive_files if f["name"] == selected_file_name), None)
                    if selected_file:
                        file_name, file_buffer = get_drive_files_in_memory(drive_service, [selected_file])[0]
                        file_buffer.name = file_name
                        file_buffer.type = "application/pdf"
                        uploaded_report = file_buffer
                        st.success(f"✅ Loaded '{file_name}' from Drive.")
                        # Clear session state so UI hides again
                        del st.session_state["drive_mode"]



with col2:
    st.subheader("📧 Email")
    uploaded_email = st.file_uploader("Upload Email PDF (PDF)", type="pdf", key="email")

    if st.button("📂 From Drive (Email)", key="drive_email_btn"):
        st.session_state.drive_mode = "email"

    if st.session_state.get("drive_mode") == "email":
        if "google_creds" not in st.session_state:
            st.warning("Please authorize Google Drive access using the expander above.")
        else:
            drive_service = build_drive_service()
            drive_files = list_drive_pdfs(drive_service)
            if drive_files:
                selected_file_name = st.selectbox("Select Email PDF from Drive", [f["name"] for f in drive_files], key="email_drive_file")
                if st.button("✅ Use Selected Email PDF from Drive", key="use_drive_email"):
                    selected_file = next((f for f in drive_files if f["name"] == selected_file_name), None)
                    if selected_file:
                        file_name, file_buffer = get_drive_files_in_memory(drive_service, [selected_file])[0]
                        file_buffer.name = file_name
                        file_buffer.type = "application/pdf"
                        uploaded_email = file_buffer
                        st.success(f"✅ Loaded '{file_name}' from Drive.")
                        del st.session_state["drive_mode"]

with col3:
    st.subheader("📣 SMM Report")
    uploaded_smm_report = st.file_uploader("Upload SMM Report (PDF)", type="pdf", key="smm_report")

    if st.button("📂 From Drive (SMM)", key="drive_smm_btn"):
        st.session_state.drive_mode = "smm"

    if st.session_state.get("drive_mode") == "smm":
        if "google_creds" not in st.session_state:
            st.warning("Please authorize Google Drive access using the expander above.")
        else:
            drive_service = build_drive_service()
            drive_files = list_drive_pdfs(drive_service)
            if drive_files:
                selected_file_name = st.selectbox("Select SMM Report from Drive", [f["name"] for f in drive_files], key="smm_drive_file")
                if st.button("✅ Use Selected SMM Report from Drive", key="use_drive_smm"):
                    selected_file = next((f for f in drive_files if f["name"] == selected_file_name), None)
                    if selected_file:
                        file_name, file_buffer = get_drive_files_in_memory(drive_service, [selected_file])[0]
                        file_buffer.name = file_name
                        file_buffer.type = "application/pdf"
                        uploaded_smm_report = file_buffer
                        st.success(f"✅ Loaded '{file_name}' from Drive.")
                        del st.session_state["drive_mode"]

with col4:
    st.subheader("🚀 QBR Report")
    uploaded_qbr = st.file_uploader("Upload QBR Report (PDF)", type="pdf", key="qbr_report")

    if st.button("📂 From Drive (QBR)", key="drive_qbr_btn"):
        st.session_state.drive_mode = "qbr"

    if st.session_state.get("drive_mode") == "qbr":
        if "google_creds" not in st.session_state:
            st.warning("Please authorize Google Drive access using the expander above.")
        else:
            drive_service = build_drive_service()
            drive_files = list_drive_pdfs(drive_service)
            if drive_files:
                selected_file_name = st.selectbox("Select QBR Report from Drive", [f["name"] for f in drive_files], key="qbr_drive_file")
                if st.button("✅ Use Selected QBR Report from Drive", key="use_drive_qbr"):
                    selected_file = next((f for f in drive_files if f["name"] == selected_file_name), None)
                    if selected_file:
                        file_name, file_buffer = get_drive_files_in_memory(drive_service, [selected_file])[0]
                        file_buffer.name = file_name
                        file_buffer.type = "application/pdf"
                        uploaded_qbr = file_buffer
                        st.success(f"✅ Loaded '{file_name}' from Drive.")
                        del st.session_state["drive_mode"]


# ⛔ Ensure only one PDF is uploaded at a time
uploaded_files = [uploaded_report, uploaded_email, uploaded_smm_report]
uploaded_files = [f for f in uploaded_files if f is not None]

if len(uploaded_files) > 1:
    st.warning("⚠️ Please upload only one PDF at a time (Monthly Report OR Email OR SMM Report).")
    st.stop()


# Process uploaded files
if uploaded_report or uploaded_email or uploaded_smm_report or uploaded_qbr: # Added uploaded_qbr
    report_percentage = None
    email_percentage = None
    smm_percentage = None
    qbr_percentage = None 

    if uploaded_report:
        st.info("🔄 Processing Monthly Report...")
        with st.spinner("Uploading Report..."):
            report_gemini_file = upload_pdf_to_gemini(uploaded_report)
            if report_gemini_file:
                st.success("✅ Report PDF uploaded successfully")
                with st.spinner("Getting report evaluation from AI..."):
                    report_scores = get_scores_from_gemini_pdf(
                        report_gemini_file, PROMPT_TEMPLATE_REPORT, max_scores_report, 'report'
                    )
                    if report_scores:
                        report_percentage = display_results(report_scores, "Report Deck", "report")
                    else:
                        st.error("❌ Could not parse report evaluation results.")
                try:
                    genai.delete_file(report_gemini_file.name)
                except:
                    pass

    elif uploaded_email:
        st.info("🔄 Processing Email...")
        with st.spinner("Uploading Email..."):
            email_gemini_file = upload_pdf_to_gemini(uploaded_email)
            if email_gemini_file:
                st.success("✅ Email PDF uploaded successfully")
                with st.spinner("Getting email evaluation from AI..."):
                    email_scores = get_scores_from_gemini_pdf(
                        email_gemini_file, PROMPT_TEMPLATE_EMAIL, max_scores_email, 'email'
                    )
                    if email_scores:
                        email_percentage = display_results(email_scores, "Email", "email")
                    else:
                        st.error("❌ Could not parse email evaluation results.")
                try:
                    genai.delete_file(email_gemini_file.name)
                except:
                    pass

    elif uploaded_smm_report:
        st.info("🔄 Processing SMM Report...")
        with st.spinner("Uploading SMM Report..."):
            smm_gemini_file = upload_pdf_to_gemini(uploaded_smm_report)
            if smm_gemini_file:
                st.success("✅ SMM Report PDF uploaded successfully")
                with st.spinner("Getting SMM report evaluation from AI..."):
                    smm_scores = get_scores_from_gemini_pdf(
                        smm_gemini_file, PROMPT_TEMPLATE_SMM_REPORT, max_scores_smm_report, 'smm'
                    )
                    if smm_scores:
                        smm_percentage = display_results(smm_scores, "SMM Report", "smm")
                    else:
                        st.error("❌ Could not parse SMM report evaluation results.")
                try:
                    genai.delete_file(smm_gemini_file.name)
                except:
                    pass

    elif uploaded_qbr: # New block for QBR
        st.info("🔄 Processing QBR...")
        with st.spinner("Uploading QBR..."):
            qbr_gemini_file = upload_pdf_to_gemini(uploaded_qbr)
            if qbr_gemini_file:
                st.success("✅ QBR PDF uploaded successfully")
                with st.spinner("Getting QBR evaluation from AI..."):
                    qbr_scores = get_scores_from_gemini_pdf(
                        qbr_gemini_file, PROMPT_TEMPLATE_QBR, max_scores_qbr, 'qbr'
                    )
                    if qbr_scores:
                        qbr_percentage = display_results(qbr_scores, "QBR Deck", "qbr")
                    else:
                        st.error("❌ Could not parse QBR evaluation results.")
                try:
                    genai.delete_file(qbr_gemini_file.name)
                except:
                    pass

with st.sidebar:
    st.header("💬 Ask Your PDF")

    if uploaded_report or uploaded_email or uploaded_smm_report or uploaded_qbr:
        selected_pdf = uploaded_report or uploaded_email or uploaded_smm_report or uploaded_qbr
        extracted_text = extract_text_from_pdf(selected_pdf)

        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        user_question = st.text_input("Ask something about this PDF...")

        if st.button("Ask"):
            if user_question.strip() != "":
                with st.spinner("Gemini is thinking..."):
                    answer = generate_gemini_response(user_question, extracted_text)
                    st.session_state.chat_history.append(("You", user_question))
                    st.session_state.chat_history.append(("Gemini", answer))

        # Display chat history
        for sender, msg in st.session_state.chat_history:
            st.markdown(f"**{sender}:** {msg}")

    else:
        st.info("Upload a PDF to start chatting with it.")