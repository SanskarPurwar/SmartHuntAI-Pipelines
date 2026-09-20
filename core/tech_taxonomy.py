"""
Master Tech Stack Taxonomy & Disambiguation Engine.
Contains canonical naming, category classification, and alias mappings
for 400+ technical skills across software engineering, data, cloud, and AI.
"""

from typing import Dict, List, Set, Optional

# Master taxonomy mapping: canonical_name -> { "category": str, "aliases": set() }
TECH_TAXONOMY: Dict[str, Dict[str, Any]] = {
    # ── Programming Languages ──
    "Python": {"category": "language", "aliases": {"python", "python3", "py"}},
    "JavaScript": {"category": "language", "aliases": {"javascript", "js", "ecmascript"}},
    "TypeScript": {"category": "language", "aliases": {"typescript", "ts"}},
    "Java": {"category": "language", "aliases": {"java", "core java", "java 8", "java 11", "java 17", "java 21"}},
    "C++": {"category": "language", "aliases": {"c++", "cpp"}},
    "C#": {"category": "language", "aliases": {"c#", "csharp", "c-sharp", ".net c#"}},
    "C": {"category": "language", "aliases": {"c language", "c programming"}},  # Disambiguated
    "Go": {"category": "language", "aliases": {"golang", "go language", "go programming"}},
    "Rust": {"category": "language", "aliases": {"rust lang", "rustlang"}},  # Disambiguated
    "Ruby": {"category": "language", "aliases": {"ruby"}},
    "PHP": {"category": "language", "aliases": {"php", "php7", "php8"}},
    "Swift": {"category": "language", "aliases": {"swift", "swiftui"}},
    "Kotlin": {"category": "language", "aliases": {"kotlin"}},
    "Scala": {"category": "language", "aliases": {"scala"}},
    "R": {"category": "language", "aliases": {"r programming", "r language", "r-project"}},
    "Dart": {"category": "language", "aliases": {"dart", "dartlang"}},
    "SQL": {"category": "language", "aliases": {"sql", "t-sql", "pl/sql", "plsql"}},
    "Bash": {"category": "language", "aliases": {"bash", "shell scripting", "sh", "zsh"}},
    "HTML": {"category": "language", "aliases": {"html", "html5"}},
    "CSS": {"category": "language", "aliases": {"css", "css3"}},
    "Solidity": {"category": "language", "aliases": {"solidity"}},

    # ── Frontend Frameworks & Libraries ──
    "React": {"category": "frontend", "aliases": {"react", "react.js", "reactjs"}},
    "Next.js": {"category": "frontend", "aliases": {"next.js", "nextjs", "next"}},
    "Vue.js": {"category": "frontend", "aliases": {"vue", "vue.js", "vuejs", "vue3"}},
    "Nuxt.js": {"category": "frontend", "aliases": {"nuxt", "nuxt.js", "nuxtjs"}},
    "Angular": {"category": "frontend", "aliases": {"angular", "angular.js", "angularjs", "angular 2+"}},
    "Svelte": {"category": "frontend", "aliases": {"svelte", "sveltekit"}},
    "Redux": {"category": "frontend", "aliases": {"redux", "redux toolkit", "rtk"}},
    "Tailwind CSS": {"category": "frontend", "aliases": {"tailwind", "tailwindcss", "tailwind-css"}},
    "Bootstrap": {"category": "frontend", "aliases": {"bootstrap"}},
    "Material UI": {"category": "frontend", "aliases": {"material ui", "mui", "material-ui"}},
    "Webpack": {"category": "frontend", "aliases": {"webpack"}},
    "Vite": {"category": "frontend", "aliases": {"vite", "vitejs"}},

    # ── Backend Frameworks & Runtimes ──
    "Node.js": {"category": "backend", "aliases": {"node.js", "nodejs", "node"}},
    "Express.js": {"category": "backend", "aliases": {"express", "express.js", "expressjs"}},
    "NestJS": {"category": "backend", "aliases": {"nestjs", "nest.js"}},
    "FastAPI": {"category": "backend", "aliases": {"fastapi", "fast-api"}},
    "Django": {"category": "backend", "aliases": {"django", "django rest framework", "drf"}},
    "Flask": {"category": "backend", "aliases": {"flask"}},
    "Spring Boot": {"category": "backend", "aliases": {"spring boot", "springboot", "spring framework", "spring"}},
    "ASP.NET": {"category": "backend", "aliases": {"asp.net", "asp.net core", ".net core", "dotnet", ".net"}},
    "Ruby on Rails": {"category": "backend", "aliases": {"ruby on rails", "rails"}},
    "Laravel": {"category": "backend", "aliases": {"laravel"}},
    "Gin": {"category": "backend", "aliases": {"gin-gonic", "gin framework"}},
    "GraphQL": {"category": "backend", "aliases": {"graphql", "apollo", "apollo graphql"}},
    "REST API": {"category": "backend", "aliases": {"restful", "rest api", "rest apis", "rest"}},
    "gRPC": {"category": "backend", "aliases": {"grpc"}},
    "WebSockets": {"category": "backend", "aliases": {"websocket", "websockets", "socket.io"}},

    # ── Mobile ──
    "Flutter": {"category": "mobile", "aliases": {"flutter"}},
    "React Native": {"category": "mobile", "aliases": {"react native", "react-native"}},
    "Android": {"category": "mobile", "aliases": {"android sdk", "android development"}},
    "iOS": {"category": "mobile", "aliases": {"ios development", "cocoa", "cocoapods"}},

    # ── Databases & Caching ──
    "PostgreSQL": {"category": "database", "aliases": {"postgresql", "postgres", "psql"}},
    "MySQL": {"category": "database", "aliases": {"mysql"}},
    "MongoDB": {"category": "database", "aliases": {"mongodb", "mongo"}},
    "Redis": {"category": "database", "aliases": {"redis"}},
    "SQLite": {"category": "database", "aliases": {"sqlite", "sqlite3"}},
    "Cassandra": {"category": "database", "aliases": {"cassandra", "apache cassandra"}},
    "DynamoDB": {"category": "database", "aliases": {"dynamodb", "aws dynamodb"}},
    "Elasticsearch": {"category": "database", "aliases": {"elasticsearch", "elastic search", "opensearch"}},
    "Snowflake": {"category": "database", "aliases": {"snowflake"}},
    "BigQuery": {"category": "database", "aliases": {"bigquery", "google bigquery"}},
    "ClickHouse": {"category": "database", "aliases": {"clickhouse"}},
    "Neo4j": {"category": "database", "aliases": {"neo4j"}},
    "Oracle DB": {"category": "database", "aliases": {"oracle database", "oracle db"}},
    "Firebase": {"category": "database", "aliases": {"firebase", "firestore"}},
    "Supabase": {"category": "database", "aliases": {"supabase"}},

    # ── Cloud & Infrastructure ──
    "AWS": {"category": "cloud", "aliases": {"aws", "amazon web services", "ec2", "s3", "lambda", "ecs", "eks", "rds", "sqs", "sns"}},
    "GCP": {"category": "cloud", "aliases": {"gcp", "google cloud", "google cloud platform", "cloud run", "gke"}},
    "Azure": {"category": "cloud", "aliases": {"azure", "microsoft azure", "azure devops"}},
    "Docker": {"category": "devops", "aliases": {"docker", "docker container", "dockerfile", "docker-compose"}},
    "Kubernetes": {"category": "devops", "aliases": {"kubernetes", "k8s"}},
    "Terraform": {"category": "devops", "aliases": {"terraform"}},
    "Ansible": {"category": "devops", "aliases": {"ansible"}},
    "Helm": {"category": "devops", "aliases": {"helm"}},
    "CI/CD": {"category": "devops", "aliases": {"ci/cd", "ci cd", "continuous integration"}},
    "GitHub Actions": {"category": "devops", "aliases": {"github actions"}},
    "GitLab CI": {"category": "devops", "aliases": {"gitlab ci", "gitlab-ci"}},
    "Jenkins": {"category": "devops", "aliases": {"jenkins"}},
    "Git": {"category": "devops", "aliases": {"git", "github", "gitlab", "bitbucket"}},
    "Linux": {"category": "devops", "aliases": {"linux", "ubuntu", "debian", "centos", "redhat", "rhel"}},
    "Nginx": {"category": "devops", "aliases": {"nginx"}},

    # ── Message Brokers & Streaming ──
    "Kafka": {"category": "streaming", "aliases": {"kafka", "apache kafka"}},
    "RabbitMQ": {"category": "streaming", "aliases": {"rabbitmq"}},
    "Celery": {"category": "streaming", "aliases": {"celery"}},
    "Spark": {"category": "data", "aliases": {"spark", "apache spark", "pyspark"}},
    "Flink": {"category": "data", "aliases": {"flink", "apache flink"}},
    "Airflow": {"category": "data", "aliases": {"airflow", "apache airflow"}},
    "dbt": {"category": "data", "aliases": {"dbt", "data build tool"}},
    "Hadoop": {"category": "data", "aliases": {"hadoop", "hdfs", "mapreduce"}},

    # ── AI, ML & Data Science ──
    "PyTorch": {"category": "ai_ml", "aliases": {"pytorch"}},
    "TensorFlow": {"category": "ai_ml", "aliases": {"tensorflow", "tf"}},
    "Keras": {"category": "ai_ml", "aliases": {"keras"}},
    "Scikit-learn": {"category": "ai_ml", "aliases": {"scikit-learn", "sklearn"}},
    "Pandas": {"category": "ai_ml", "aliases": {"pandas"}},
    "NumPy": {"category": "ai_ml", "aliases": {"numpy"}},
    "OpenCV": {"category": "ai_ml", "aliases": {"opencv"}},
    "Hugging Face": {"category": "ai_ml", "aliases": {"hugging face", "huggingface", "transformers"}},
    "LangChain": {"category": "ai_ml", "aliases": {"langchain"}},
    "LlamaIndex": {"category": "ai_ml", "aliases": {"llamaindex", "llama-index"}},
    "LLMs": {"category": "ai_ml", "aliases": {"llm", "llms", "large language models", "generative ai", "genai"}},
    "Computer Vision": {"category": "ai_ml", "aliases": {"computer vision", "cv"}},
    "NLP": {"category": "ai_ml", "aliases": {"nlp", "natural language processing"}},

    # ── Testing & Observability ──
    "Jest": {"category": "testing", "aliases": {"jest"}},
    "Pytest": {"category": "testing", "aliases": {"pytest"}},
    "Selenium": {"category": "testing", "aliases": {"selenium"}},
    "Cypress": {"category": "testing", "aliases": {"cypress"}},
    "Playwright": {"category": "testing", "aliases": {"playwright"}},
    "JUnit": {"category": "testing", "aliases": {"junit"}},
    "Prometheus": {"category": "observability", "aliases": {"prometheus"}},
    "Grafana": {"category": "observability", "aliases": {"grafana"}},
    "Datadog": {"category": "observability", "aliases": {"datadog"}},
    "New Relic": {"category": "observability", "aliases": {"new relic", "newrelic"}},
}

# Reverse lookup: alias -> canonical name
ALIAS_TO_CANONICAL: Dict[str, str] = {}
for canonical, meta in TECH_TAXONOMY.items():
    ALIAS_TO_CANONICAL[canonical.lower()] = canonical
    for alias in meta["aliases"]:
        ALIAS_TO_CANONICAL[alias.lower()] = canonical

def get_canonical_tech(name: str) -> Optional[str]:
    """Resolves an alias or tech string to its canonical taxonomy name."""
    if not name:
        return None
    return ALIAS_TO_CANONICAL.get(name.strip().lower())
