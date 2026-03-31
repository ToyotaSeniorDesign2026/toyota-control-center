# RAG Evaluation Roadmap: Current Trends and Taxonomy

This document categorizes the current state of Retrieval-Augmented Generation (RAG) evaluation based on the ArXiv search results. Evaluation is diversifying from simple text accuracy into functional, multimodal, and security-focused domains.

## 1. Taxonomy of RAG Evaluation

### A. Semantic & Pipeline Health (The "RAG Triad")
Focuses on the relationship between query, context, and response.
- **Key Paper:** *Ragas: Automated Evaluation of Retrieval Augmented Generation*
- **Target:** General QA and chat systems.
- **Approach:** Using LLMs to judge faithfulness and relevance without human ground truths.

### B. Functional & Domain-Specific Correctness
Focuses on whether the RAG output actually performs a task successfully.
- **Key Paper:** *EVOR: Evolving Retrieval for Code Generation*
- **Target:** Software engineering and programming.
- **Approach:** Execution-based evaluation (Pass@k) using unit tests.

### C. Multimodal RAG
Focuses on RAG systems that generate non-textual outputs.
- **Key Paper:** *AR-RAG: Autoregressive Retrieval Augmentation for Image Generation*
- **Target:** Visual content generation.
- **Approach:** Benchmarked using DPG-Bench and GenEval for image-text alignment.

### D. Security & Privacy Benchmarking
Focuses on the vulnerabilities of the RAG data store.
- **Key Paper:** *Riddle Me This! Stealthy Membership Inference for RAG*
- **Target:** Data privacy and adversarial robustness.
- **Approach:** Benchmarking via Membership Inference Attacks (MIA) to see if private documents can be leaked.

### E. Application-Specific Benchmarks
Focuses on specific professional workflows.
- **Key Paper:** *Automated Literature Review Using NLP Techniques and RAG*
- **Target:** Academic research automation.
- **Approach:** Using ROUGE scores and SciTLDR datasets to measure summarization quality.

---

## 2. Summary of ArXiv Identifiers
| Category | Paper Title | ArXiv ID |
| :--- | :--- | :--- |
| **Semantic** | Ragas: Automated Evaluation of RAG | 2309.15217 |
| **Code** | EVOR: Evolving Retrieval for Code Generation | 2402.12317 |
| **Images** | AR-RAG: Autoregressive Retrieval for Image Gen | 2506.06962 |
| **Security** | Riddle Me This! Membership Inference for RAG | 2502.00306 |
| **Lit Review** | Automated Literature Review Using RAG | 2411.18583 |
