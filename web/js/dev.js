export const devData = {
    name: 'Ustela Sukesh Reddy',
    company: 'Tetrifox',
    role: 'Software Developer - Intern',
    focus: 'coding',
    resume: `# Ustela Sukesh Reddy
**B.Tech — Electrical Engineering | National Institute of Technology Durgapur**  
**Phone:** +91-9390163768 | **Email:** [sukeshreddyustela@gmail.com](mailto:sukeshreddyustela@gmail.com) | **Location:** Suryapet, Telangana – 508206, India  
**LinkedIn:** [linkedin.com/in/sukesh-reddy-ustela](https://linkedin.com/in/sukesh-reddy-ustela) | **GitHub:** [github.com/suke2004](https://github.com/suke2004)

---

## Educational Qualification

| Degree / Examination | Institution / Board | Year | CGPA / Percentage |
| :--- | :--- | :--- | :--- |
| **B.Tech (Electrical Engineering)** | National Institute of Technology Durgapur | 2023 – Present | **7.28 / 10.0** (Sem 1–6) |
| **Class XII (Intermediate)** | Telangana State Board of Intermediate Education | 2023 | **96.9%** |
| **Class X (SSC)** | Board of Secondary Education, Telangana State | 2021 | **10.0 / 10.0** |

*Semester SGPA Breakdown:* Sem 1: 7.96 | Sem 2: 7.95 | Sem 3: 6.67 | Sem 4: 6.96 | Sem 5: 6.76 | Sem 6: 7.57

---

## Work Experience

### Graduate Engineer Trainee Intern — Reliance Industries Limited (Nagothane Mfg. Division)
*May 2026 – July 2026 | Nagothane, Maharashtra*
* Architected and deployed a centralized IIoT telemetry service connecting 12 Schneider Electric UPS systems and 22 Masstech battery chargers across 6 plant locations, converting Modbus RTU/RS-485 serial data to MQTT via industrial edge gateways for real-time electrical telemetry.
* Conducted a 3-way architectural trade-off analysis (Plant LAN vs. Wireless Cloud Gateway vs. SNMP/NMC) on 5-year TCO, latency, and WAN outage resilience; recommended a hybrid edge architecture preserving local alerting during network failures.
* Built a SCADA-style monitoring dashboard prototype enforcing Purdue-model network segmentation and IEC 62443 cybersecurity standards; delivered deployment roadmap and bill of materials (13 edge gateways, 18 RS-485 converters).
* Owned the feature end to end, from architecture to production rollout: eliminated manual log-book rounds in hazardous plant zones by routing live telemetry into automated trend analysis, enabling predictive condition-based maintenance.

### Open Source Contributor — Hacktoberfest 2025 & GirlScript Summer of Code (GSSoC)
*October 2025 – November 2025 | Remote*
* Contributed 25+ merged pull requests across public developer tooling, browser extensions, and AI agent repositories with automated CI/CD validation via GitHub Actions; practiced code review and collaborative development on public codebases.

---

## Projects

### SuperAgent (AgentRouter Mobile) — Offline-First Enterprise LLM Client
*React Native (Expo SDK 57), TypeScript, Expo Router, SQLite (FTS5 + SQLCipher), Android Keystore, Zustand, Jest* | [Source Code](https://github.com/suke2004/SuperAgent)
* **Transport & Protocol Normalization:** Architected an offline-first mobile AI client (36k+ LOC TypeScript) normalizing Anthropic (\`POST /v1/messages\`) and OpenAI (\`POST /v1/chat/completions\`) streaming wire protocols behind a unified SSE transport layer with exponential retry backoff and transparent network failover.
* **Encrypted Storage & Sub-10ms Search:** Engineered an encrypted-at-rest local transcript store using SQLCipher and SQLite Full-Text Search (FTS5), enabling instant conversation indexing and sub-10ms cross-chat retrieval without cloud dependency or server costs.
* **Hardware-Backed Security & Sandboxing:** Eliminated API credential leakage by storing bearer tokens exclusively in the hardware-backed Android Keystore via \`expo-secure-store\`, and isolated untrusted code execution and artifact rendering in a sandboxed WebView strictly enforcing \`default-src 'none'\`.
* **Tool Execution & MCP Protocol:** Implemented a Model Context Protocol (MCP) JSON-RPC client over HTTP/SSE supporting runtime tool discovery, concurrent pre-approved execution, and a plan-mode gate preventing rogue write operations without explicit user confirmation.
* **Production Quality & Test Coverage:** Built comprehensive test infrastructure with 38 test suites and 948 automated Jest unit tests across stream decoders, database migrations, and turn lifecycles, enforcing zero-regression CI/CD via GitHub Actions.

### OSS-Community-Agent — Autonomous RAG & Multi-Agent Support System
*Python 3.11, Portia AI, LangChain, ChromaDB, Groq LPU, Streamlit, PRAW, SQLite, PyTest, GitHub Actions* | [Source Code](https://github.com/suke2004/OSS-Community-Agent)
* **Autonomous RAG & Fast Inference:** Engineered an autonomous multi-agent support pipeline (13k+ LOC Python) indexing documentation into ChromaDB with semantic chunking and top-4 similarity retrieval, paired with Groq LPU inference for sub-second, context-grounded response generation.
* **Human-in-the-Loop Governance:** Built a fail-safe governance layer queuing model responses in SQLite for maintainer review whenever cosine similarity confidence fell below safety thresholds, preventing hallucinated advice and eliminating unauthorized repository actions.
* **Automated Triage & Social Ingestion:** Automated community question scraping and thread triage across Reddit using PRAW with strict rate-limit handling, automatic duplicate detection, and semantic intent classification.
* **Interactive Telemetry Dashboard:** Developed a real-time Streamlit operations dashboard featuring an approval workflow queue, token usage metrics, response latency monitoring, and complete audit logging for community maintainers.
* **Validation & National Recognition:** Validated end-to-end pipeline reliability with 41 PyTest suites across cross-platform CI/CD runners (Ubuntu, macOS, Windows); recognized as a Top 10 Finalist nationwide out of 200+ engineering teams at AgentHack 2025.

### Smart Adaptive Load Balancer
*Go (Golang), HTTP Reverse Proxy, Goroutines, Channels, sync/atomic, HTML5/CSS3 Dashboard* | [Source Code](https://github.com/suke2004/load-balancer)
* **High-Throughput Concurrency:** Engineered a Layer-7 reverse proxy load balancer from scratch in Go utilizing goroutines, non-blocking channels, and atomic primitives, sustaining 6,600+ requests/second with zero dropped connections under 100 concurrent clients.
* **Adaptive Latency-Aware Routing:** Implemented four dynamic routing algorithms (Round-Robin, Least-Connections, Weighted, and Adaptive), using an exponential moving average of live backend response times to route away from degraded nodes and maintain p50 latency at 13ms (p99 44ms).
* **Active Health Checks & Fault Tolerance:** Built an asynchronous background health-probing engine that continuously evaluates upstream server responsiveness, evicting unhealthy instances from the active pool and re-admitting them post-recovery without service interruption.
* **Real-Time Visual Monitoring:** Developed an embedded web dashboard visualizing cluster topology, live throughput (RPS), active connection states, and per-node latency graphs for real-time observability.
* **Configurability & Benchmarking:** Architected modular reverse-proxy middleware with configurable timeouts, connection pooling, and circuit breaking; validated architectural stability through comprehensive Go unit tests and automated load-testing benchmarks.

---

## Technical Skills Summary

* **AI & Agentic Systems:** Multi-Agent Architectures, LangChain, Portia AI, RAG Pipelines, Vector DBs (ChromaDB), Embeddings (sentence-transformers), Context Engineering, Prompt Optimization, Model Context Protocol (MCP), Human-in-the-Loop Governance, Guardrails, Groq LPU, OpenAI & Anthropic Wire Transports
* **Languages & Frameworks:** Python, Go (Golang), TypeScript, JavaScript, C/C++, React Native (Expo), Node.js, Express.js, FastAPI, Django REST Framework, RESTful APIs, SQL
* **Databases & Storage:** PostgreSQL, MongoDB (ACID Transactions), SQLite (FTS5 Search, SQLCipher), Redis, ChromaDB
* **Cloud, DevOps & Systems:** Docker, Git/GitHub Actions (CI/CD), Linux/Unix, Concurrency (Goroutines/Channels), Reverse Proxies, Google Cloud Platform (79 Skill Badges, 212 Hands-on Labs)
* **Techno-Commercial & Soft Skills:** Technical Solutioning & Presales Support, Stakeholder Connect, Techno-Commercial Feasibility & Cost-Benefit Analysis, Cross-Functional Collaboration, Technical Documentation, Presentation & Negotiation

---

## Achievements & Certifications

* **Top 10 Finalist — AgentHack 2025:** Secured a Top 10 position nationwide among 200+ engineering teams through rapid prototyping and collaborative technical execution.
* **Google Cloud Arcade — Novice Tier:** Earned 79 skill badges and completed 212 hands-on labs, 62 courses, and 14 cloud challenges across GCP infrastructure and services.
* **Core Organizing Committee — Smart India Internal Hackathon:** Organized institute-wide technical workshops and the Smart India Internal Hackathon, driving hands-on participation across engineering disciplines.
* **Infosys Springboard AI Track:** Engineered *AI-EnviroScan*, an automated pollution source classification capstone with multi-API telemetry ingestion, ML benchmarking, and FastAPI + Streamlit deployment.

---

## Positions of Responsibility

* **Technical Head — CCA (R&D Cell), NIT Durgapur** *(May 2024 – Present)*: Mentored 25+ juniors across 9+ national hackathons on embedded systems, IoT, and AI/ML; conducted architecture reviews and debugging sessions.
* **GeeksforGeeks Campus Mantri — NIT Durgapur:** Led campus technical outreach, workshops, and coding events reaching 100+ students; authored learning material and strengthened the peer programming culture.
* **Convener — Ampere, EE Departmental Society, NIT Durgapur** *(May 2025 – Present)*: Co-founded Ampere with faculty; defined the strategic roadmap and organized technical workshops, industrial guest lectures, and hackathons.
* **Unit Leader — NSS, NIT Durgapur** *(Aug 2024 – Present)*: Coordinated community social-awareness campaigns and represented NIT Durgapur NSS at institutional and national-level outreach events.
`,
    objectives: `# Tetrifox — Job Description: Software Development Engineer I (Internship to PPO)

**Company:** Tetrifox (Headquarters: Rotterdam, Netherlands)  
**Role Title:** Software Development Engineer I / Software Developer – Intern \`[NITD]\`  
**Department:** Product Engineering  
**Employment Type:** 6-Month Internship with Performance-Based PPO (Full-Time)  
**Location:** Remote (India)  
**Compensation:**  
* **Internship Stipend:** ₹25,000 / month  
* **Full-Time PPO CTC:** ₹12 LPA (12,00,000 INR per annum)  

---

## About Tetrifox

Tetrifox is a modern product engineering partner based in the Netherlands. We embed modular, cross-functional product teams—called **Minos** (Strategic Consultancy/PO + Technical Leadership + Engineering across Dev, Ops, and QA)—directly into scaling European startups and enterprises. 

We bridge the gap between business ambition and technical execution, taking products from idea to production in weeks, not quarters. Our core thesis: *"AI is an engineering problem, not a strategy problem."* We build production-ready applications with strict scope sizing, unit cost-per-run monitoring, and business-first validation.

---

## About the Role

We are looking for a **Software Development Engineer I (Intern)** to join one of our Mino teams and kickstart a high-trajectory engineering career. Whether you are fresh out of university or in your final year, you will learn faster here than anywhere else because you will be shipping real software for real products from day one.

At Tetrifox, junior engineers aren’t sidelined with busywork or synthetic toy tasks. You will work inside an embedded product team alongside experienced engineers, a Technical Lead, and a Product Owner. You will receive meaningful code reviews, pair with senior architects on hard problems, and see your features reach production. 

This is an **internship-friendly role** welcoming candidates with **0–4 years of experience**, operating remotely from India within a globally distributed Mino.

---

## Key Responsibilities

* **Feature Engineering:** Collaborate directly within your Mino unit to design, build, and maintain software features under the direct mentorship of senior engineers and tech leads.
* **Code Craftsmanship:** Write clean, readable, well-tested, and well-structured code adhering to modern software engineering best practices, coding standards, and architectural design patterns.
* **Code Review & Feedback:** Actively participate in peer code reviews—absorbing feedback constructively while developing an instinct for high code quality, performance, and security.
* **Root-Cause Debugging:** Help investigate, troubleshoot, and resolve software defects, mastering telemetry analysis, logging, and root-cause analysis along the way.
* **Agile & Mino Rituals:** Actively contribute in sprint planning, daily stand-ups, backlog refinement, and retrospectives—bringing your ideas and perspective to the table as a full team member.
* **Technological Curiosity:** Stay ahead of modern tech trends—explore new AI frameworks, libraries, tools, and developer techniques, and bring high-leverage ideas back to the engineering team.
* **Documentation & Knowledge Sharing:** Document your architecture, API schemas, and development workflows to foster transparent collaboration and mentor fellow junior engineers.

---

## Requirements

* **Experience:** 0–4 years of software development experience (internship experience, open-source work, and serious personal projects count).
* **Education:** Bachelor's degree in Computer Science, Software Engineering, Electrical Engineering, or a related discipline (or equivalent practical self-taught experience).
* **Core Languages:** Foundational programming knowledge in at least one modern language: **Python, JavaScript/TypeScript, Go, C#, or Java**.
* **Fundamentals:** Solid grasp of computer science fundamentals, data structures, algorithms, and software design principles.
* **Version Control:** Hands-on familiarity with Git, GitHub workflows, branch management, and modern CI/CD tooling.
* **Mindset:** Strong first-principles problem-solving mindset, intellectual curiosity, and an eagerness to take extreme ownership.
* **Communication:** Clear, concise written and verbal communication skills—able to articulate technical tradeoffs, ask targeted questions, and collaborate seamlessly across remote time zones.

---

## Nice to Have (Bonus Points)

* **Initiative & Portfolio:** Personal projects, hackathon prototypes, or open-source contributions demonstrating genuine builder initiative.
* **AI & Agentic Systems:** Familiarity with LLM APIs (OpenAI, Anthropic, Groq), RAG pipelines, vector embeddings, or agentic workflows.
* **Frontend Knowledge:** Experience building user interfaces with React, React Native, Next.js, Vue, or Angular.
* **Testing Discipline:** Experience with automated unit testing, integration tests, or Test-Driven Development (TDD) concepts (Jest, PyTest, Go test).
* **Cloud & Systems:** Exposure to cloud infrastructure (AWS, GCP, Azure), Docker containerization, reverse proxies, or microservices architecture.
* **Agile Delivery:** Familiarity with Agile, Scrum, or Kanban methodologies.

---

## What Tetrifox Offers

* **High-Impact Career Growth:** Direct conversion path from 6-month intern to full-time Software Development Engineer I (12 LPA CTC), with clear milestones for progression to SDE II and beyond based on merit, not tenure.
* **Competitive Compensation:** ₹25,000/month internship stipend + ₹12,00,000 INR per annum full-time PPO package.
* **100% Remote & Autonomy:** Fully remote work from anywhere in India with flexible working hours to build your own peak productive rhythm.
* **World-Class Mentorship:** Direct pairing and code reviews with seasoned European tech leads and software architects.
* **Real Production Impact:** Work on live applications serving real end-users across European startups and scale-ups.
* **Generous Time Off & Sustainable Pace:** Vacation days, public holidays, and paid leave from day one—sustainable engineering pace is a core principle, not a slogan.
* **Team Culture:** Quarterly remote/in-person team events to connect with the humans behind the screens.
`
};

import { devLog } from './config.js';

export function autofillForTesting() {
    devLog("Autofilling form for testing...");

    // Get form elements directly from DOM
    const onboardingForm = {
        name: document.getElementById('user-name'),
        company: document.getElementById('user-company'),
        role: document.getElementById('user-role'),
        focusCheckboxes: document.querySelectorAll('input[name="focus"]'),
        resume: document.getElementById('user-resume'),
        objectives: document.getElementById('user-objectives'),
    };

    // Check if elements exist before setting values
    if (onboardingForm.name) onboardingForm.name.value = devData.name;
    if (onboardingForm.company) onboardingForm.company.value = devData.company;
    if (onboardingForm.role) onboardingForm.role.value = devData.role;

    if (onboardingForm.focusCheckboxes) {
        onboardingForm.focusCheckboxes.forEach(cb => {
            if (cb.value === devData.focus) {
                cb.checked = true;
            }
        });
    }

    if (onboardingForm.resume) onboardingForm.resume.value = devData.resume;
    if (onboardingForm.objectives) onboardingForm.objectives.value = devData.objectives;

    devLog("✅ Form autofilled successfully!");
}
