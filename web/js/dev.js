export const devData = {
    name: 'Alex Chen',
    company: 'Horizon Technologies',
    role: 'Senior Full Stack Engineer',
    focus: 'coding',
    resume: `ALEX CHEN
Senior Full Stack Engineer
Contact: alex.chen@email.com | LinkedIn | GitHub

PROFESSIONAL SUMMARY
Full Stack Engineer with 4+ years of experience building scalable web applications and cloud-native services. Expertise in React, Node.js, Python, and AWS. Proven ability to architect microservices, optimize database performance, and lead cross-functional engineering teams. Passionate about clean code, developer experience, and shipping products that delight users.

TECHNICAL SKILLS
Frontend: React, Next.js, TypeScript, Vue.js, Tailwind CSS, HTML5, CSS3
Backend: Node.js, Python, FastAPI, Express.js, GraphQL, REST APIs
Databases: PostgreSQL, MongoDB, Redis, DynamoDB, Elasticsearch
Cloud & DevOps: AWS (Lambda, ECS, S3, CloudFront), Docker, Kubernetes, Terraform, CI/CD
Tools: Git, Jira, Figma, Datadog, Sentry, Postman

PROFESSIONAL EXPERIENCE
SENIOR SOFTWARE ENGINEER | CloudStream Inc.
March 2023 – Present

Architected and built a real-time analytics dashboard serving 50K+ daily active users
Led migration from monolith to microservices, reducing deployment time by 70%
Implemented event-driven architecture with Kafka for asynchronous data processing
Mentored 3 junior engineers and established code review best practices
Technologies: React, TypeScript, Node.js, PostgreSQL, AWS, Docker, Kafka

SOFTWARE ENGINEER | DataBridge Solutions
June 2021 – February 2023

Built RESTful APIs serving financial data to 200+ enterprise clients
Designed and optimized PostgreSQL schemas, improving query performance by 45%
Developed automated testing pipeline achieving 92% code coverage
Collaborated with product and design teams on feature planning and sprint execution
Technologies: Python, FastAPI, PostgreSQL, Redis, AWS Lambda, React

JUNIOR DEVELOPER | WebCraft Studios
January 2020 – May 2021

Developed responsive web applications for e-commerce and SaaS clients
Built reusable component libraries with React and Storybook
Integrated third-party APIs including Stripe, SendGrid, and Twilio
Technologies: React, Node.js, MongoDB, Express.js, Heroku

PROJECTS
TaskFlow | AI-Powered Project Management Tool
Built a full-stack project management app with AI task prioritization
Integrated OpenAI API for smart task descriptions and time estimates
Technologies: Next.js, TypeScript, Prisma, PostgreSQL, OpenAI API

EDUCATION
Bachelor of Science in Computer Science
University of Washington, Seattle
2016 – 2020`,
    objectives: `About the job
Job Title: Senior Full Stack Engineer
Company: Horizon Technologies
Location: Remote (Full-Time)

About Us:
Horizon Technologies builds next-generation developer tools that help engineering teams ship faster and with more confidence. Our platform is used by thousands of companies worldwide.

We are looking for a Senior Full Stack Engineer to join our Platform team and help build the future of our core product.

Key Responsibilities:

Design and implement new features across our React frontend and Node.js/Python backend
Architect scalable microservices and RESTful APIs for high-traffic applications
Collaborate with product managers, designers, and other engineers to ship high-quality features
Optimize application performance, reliability, and observability
Contribute to engineering culture through code reviews, documentation, and mentoring
Participate in on-call rotation and incident response

Requirements:

4+ years of professional software engineering experience
Strong proficiency in TypeScript, React, and modern frontend development
Backend experience with Node.js or Python (FastAPI/Django)
Experience with relational databases (PostgreSQL) and caching layers (Redis)
Familiarity with cloud platforms (AWS preferred) and containerization (Docker/K8s)
Excellent communication skills and collaborative mindset
BS in Computer Science or equivalent practical experience

Nice to Have:

Experience with GraphQL, gRPC, or event-driven architectures
Familiarity with AI/ML integration and LLM APIs
Open source contributions
Experience in developer tools or platform engineering`
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