# rehab-cdss

My bachelor's thesis project — a Clinical Decision Support System (CDSS) for physical rehabilitation. The system assists clinicians by aggregating patient assessment data and generating structured rehabilitation reports with protocol and exercise recommendations.

**Project logic.** The pipeline consists of two modules. Module 1 processes raw patient data (PDFs, CSVs) from various assessments such as baropodometry, dynamometry, goniometry, and postural analysis. It produces structured test results and exports them as JSON. Module 2 is a multi-agent system (LangGraph): specialized agents handle clinical summarization, search-query generation, protocol retrieval and grading, query rewriting on weak results, clinical reasoning, exercise matching, and report generation. It uses RAG over a vector store (ChromaDB) and produces bilingual rehabilitation reports in Markdown and DOCX.

**Repository scope.** Module 1 is not included — it belongs to the partner clinic. Module 2 and the API/UI layers are available here.
