# Toyota Control Center
Toyota Control Center is a centralized platform for submitting, monitoring, and managing automated jobs across development and production environments. It is designed to support both technical and non-technical users through a web dashboard, CLI, and API-based integrations.

---

## Project Overview

The Toyota Control Center acts as a **control plane** for job execution and promotion. It allows teams to safely run scripts, workflows, or automated tasks while maintaining visibility, governance, and separation between environments.

Key goals of the project:

* Simplify job submission for non-technical users
* Provide engineers with CLI and API-based control
* Enforce environment boundaries (Dev → Prod)
* Offer clear visibility into execution status and logs

---

## Core Features

* **Web Dashboard**

  * Submit jobs through guided forms
  * View job status, logs, and history
  * Request promotion from development to production

* **Command Line Interface (CLI)**

  * Submit and manage jobs programmatically
  * View execution results and logs
  * Designed for developer workflows

* **API Integrations**

  * Submit jobs from external systems or services
  * Enable automation from tools like dashboards or schedulers

* **Environment Management**

  * Separate development and production execution
  * Promotion-based workflow to reduce risk
  * Audit-friendly job tracking

---

## User Roles

- **Admin** – Manages users, environments, permissions, and system-wide configurations.
- **Engineer** – Submits and manages jobs via CLI or API and integrates codebases.
- **Non-Technical User** – Submits jobs through the web interface and monitors execution.

---

## Deployment

This project demonstrates a full **development-to-production workflow**, including:

* Version control via GitHub
* Environment-based execution
* Promotion requests instead of direct production access

---

## Project Status

This project is being developed as part of a **Senior Design** course and focuses on realistic enterprise workflows, security boundaries, and usability.

---

## License

This project is for educational purposes.



