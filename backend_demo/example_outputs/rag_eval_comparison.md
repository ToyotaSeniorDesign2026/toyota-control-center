# RAG Evaluation Benchmarks: A Comparative Study

This document summarizes the research on Retrieval-Augmented Generation (RAG) evaluation benchmarks, focusing on two distinct methodologies.

## 1. Selected Papers

### Paper A: Ragas: Automated Evaluation of Retrieval Augmented Generation
- **Authors:** Shahul Es, Jithin James, Luis Espinosa-Anke, Steven Schockaert
- **Published:** 2023-09-26
- **Abstract:** Introduces Ragas, a reference-free evaluation framework for RAG pipelines. It provides a suite of metrics to evaluate retrieval and generation without relying on ground truth human annotations.
- **Evaluation Datasets:** WikiEval (curated from Wikipedia for validation against human labels).
- **Metrics Reported:** Faithfulness, Answer Relevance, Context Precision, Context Recall.
- **GitHub:** [explodinggradients/ragas](https://github.com/explodinggradients/ragas)

### Paper B: EVOR: Evolving Retrieval for Code Generation
- **Authors:** Hongjin Su, Shuyang Jiang, et al.
- **Published:** 2024-02-19
- **Abstract:** Develops EVOR, a pipeline for synchronous evolution of queries and knowledge bases in code generation. Introduces EVOR-BENCH, four new datasets for frequently updated libraries and long-tail languages.
- **Evaluation Datasets:** EVOR-BENCH (Four new datasets: Updated Libraries, Long-tail Languages).
- **Metrics Reported:** Execution Accuracy (Pass@k), Adaptation Gain.
- **GitHub:** [xlang-ai/arks](https://github.com/xlang-ai/arks)

---

## 2. Methodology Comparison

| Feature | **Ragas** (Es et al., 2023) | **EVOR** (Su et al., 2024) |
| :--- | :--- | :--- |
| **Evaluation Philosophy** | **Semantic & Reference-Free**: Evaluates internal consistency and quality of the RAG triad. | **Functional & Execution-Based**: Evaluates objective correctness via execution. |
| **Core Methodology** | **LLM-as-a-Judge**: Programmatic scoring using LLMs. | **Unit Testing**: Verifies code against a test suite. |
| **Primary Metrics** | Faithfulness, Answer Relevance, Context Precision. | Execution Accuracy (Pass@k). |
| **Evaluation Datasets** | WikiEval (General Knowledge). | EVOR-BENCH (Programming Specific). |
| **Human Annotation** | Minimal (designed to bypass human labeling). | High (requires human-written tests). |
| **Primary Domain** | General NLP (QA, Chat). | Programming / Code Generation. |
| **Key Advantage** | High scalability for large-scale production monitoring. | Definitive functional correctness. |

---

## 3. Search Context
These papers were selected from an ArXiv search for "Retrieval-Augmented Generation evaluation benchmarks" conducted on June 14, 2024.
