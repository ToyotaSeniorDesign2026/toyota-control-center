# **MCP Adapter: Natural Language -> AI Agent Job**

*Demo by Noah Barnard*



---



## Adapter Logic




```python
!pip install -q instructor jsonref google-genai pydantic markdown2
```

    [2K   [90m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[0m [32m177.4/177.4 kB[0m [31m4.5 MB/s[0m eta [36m0:00:00[0m
    [2K   [90m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[0m [32m50.0/50.0 kB[0m [31m3.2 MB/s[0m eta [36m0:00:00[0m
    [2K   [90m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[0m [32m45.5/45.5 kB[0m [31m2.1 MB/s[0m eta [36m0:00:00[0m
    [2K   [90m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[0m [32m358.8/358.8 kB[0m [31m12.3 MB/s[0m eta [36m0:00:00[0m
    [?25h


```python
# Imports
import instructor
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from google.colab import userdata
import os
os.environ["GEMINI_API_KEY"] = userdata.get("GEMINI_API_KEY")

# Define Environments
class Environment(str, Enum):
    DEV = "dev"
    SEMI_PROD = "semi-prod"
    PROD = "prod"

# Define Job Specification Schema
class JobSpec(BaseModel):
    name: str = Field(..., description="Unique name for the job")
    connector: str = Field(..., description="MCP connector: airflow, dbt, excel, powerpoint")
    schedule: Optional[str] = Field(None, description="Cron expression for execution")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Connector arguments")
    environment: Environment = Field(default=Environment.DEV)
    risk_score_input: List[str] = Field(default_factory=list, description="Risk tags: external_egress, pii, etc.")
    explanation: Optional[str] = Field(None, description="LLM reasoning for the configuration")

# Define Schema to Handle Complex Jobs
class JobSpecList(BaseModel):
    jobs: List[JobSpec]
```


```python
# Risk Logic
def get_risk_assessment(spec: JobSpec):
    score = 0.0
    if spec.environment in [Environment.PROD, Environment.SEMI_PROD]:
        score += 0.5
    if "external_egress" in spec.risk_score_input: # Outbound Traffic
        score += 0.3
    if "pii" in spec.risk_score_input: # Personally Identifiable Information
        score += 0.4

    risk_score = min(score, 1.0) # Risk Score up to 100%
    warning = None
    if spec.environment != Environment.DEV:
        spec.environment = Environment.DEV
        warning = "Policy Guardrail: Direct deployment to Prod/Semi-Prod blocked for new agentic AI jobs."

    return spec, risk_score, warning
```


```python
# Initialize Instructor + Gemini
client = instructor.from_provider("google/gemini-3-flash-preview")

# Converts a natural language prompt into structured MCP job specifications
def natural_language_to_job_specs(prompt: str):
    generated_specs: JobSpecList = client.create(
        response_model=JobSpecList,
        messages=[
            {"role": "system", "content": "You are the Toyota AI Control Center Adapter. Map natural language to MCP specs."},
            {"role": "user", "content": prompt},
        ],
        max_retries=3 # Try up to 3 additional times
    )

    return generated_specs

# Prints a detailed summary of generated job specifications and the assessed risk
def display_adapter_results(job_list: JobSpecList, prompt: str):

    print("--- ADAPTER RESULTS ---")
    for i, job in enumerate(job_list.jobs, start=1):
        final_spec, risk, warning = get_risk_assessment(job)

        print(f"\n--- Job #{i} ---")  # Job number at the top
        print(f"Intent: {prompt}")
        print(f"Risk Score: {risk * 100}%")
        if warning:
            print(f"WARNING: {warning}")
        print(f"Final Spec Environment: {final_spec.environment}")
        print(f"Generated Spec: {final_spec.model_dump_json(indent=2)}")

# Adapter Function - Generates MCP job specs from prompt and displays their results + risk
def run_adapter_test(prompt: str):
    display_adapter_results(natural_language_to_job_specs(prompt), prompt)
```



---



## Adapter Example: Album-of-the-Day Agent


```python
from pydantic import BaseModel
from enum import Enum
import pandas as pd
from datetime import date
from google import genai
from google.genai import types
import random
from abc import ABC, abstractmethod
from IPython.display import display, HTML
import markdown2

# Define Album Schema
class Album(BaseModel):
    title: str
    artist: str
    uri: str

# Album Research Agent - Uses Gemini + Grounded Google Search to Research Albums
class AlbumResearchAgent:
    def __init__(self, client: genai.Client, model: str = "gemini-3-flash-preview"):
        self.client = client
        self.model = model
        search_tool = types.Tool(google_search=types.GoogleSearch())
        self.config = types.GenerateContentConfig(tools=[search_tool])

    def summarize(self, album: Album) -> str:
        prompt = f"""
        You are a music expert. Given the album "{album.title}" by "{album.artist}":
        1. Use Google Search to find accurate information.
        2. Summarize the album in 3 concise sentences.
        3. Mention musical style and cultural significance.
        4. Cite sources for your information.
        """
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=self.config,
        )
        return response.text

# Define Album Selection Methods and Schema
class AlbumSelection(ABC):
    @abstractmethod
    def select_index(self, length: int) -> int:
        pass
class RandomSelection(AlbumSelection):
    def select_index(self, length: int) -> int:
        return random.randrange(length)
class DailySelection(AlbumSelection):
    def select_index(self, length: int) -> int:
        days_since_epoch = (date.today() - date(1970, 1, 1)).days
        return days_since_epoch % length
class SelectionType(str, Enum):
    RANDOM = "random"
    DAILY = "daily"
class SelectionFactory:
    @staticmethod
    def create(selection_type: SelectionType) -> AlbumSelection:
        if selection_type == SelectionType.RANDOM:
            return RandomSelection()
        if selection_type == SelectionType.DAILY:
            return DailySelection()
        raise ValueError(f"Unknown strategy: {selection_type}")

# Album Recommendation Agent - Picks and Researches an Album from the Provided CSV
class AlbumRecommendationAgent:
    def __init__(
        self,
        csv_path: str,
        research_agent: AlbumResearchAgent,
        selection_strategy: AlbumSelection
    ):
        self.df = pd.read_csv(csv_path)
        self.research_agent = research_agent
        self.selection_strategy = selection_strategy

    def _build_album_from_index(self, index: int) -> Album:
        row = self.df.iloc[index]
        return Album(title=row["Title"], artist=row["Artist"], uri=row["URI"])

    def run(self) -> dict:
        index = self.selection_strategy.select_index(len(self.df))
        album = self._build_album_from_index(index)
        description = self.research_agent.summarize(album)
        return { "album": album, "description": description }

# Album Renderer - Displays Album HTML Card with Spotify Button and Description
class AlbumRenderer:
    SPOTIFY_GREEN = "#1DB954"

    @staticmethod
    def render(result: dict):
        album: Album = result["album"]
        html_description = markdown2.markdown(result["description"])

        display(HTML(f"""
        <div style="
            max-width:700px;
            padding:25px;
            border-radius:14px;
            background:#f8f9fa;
            font-family:Arial,sans-serif;
            box-shadow:0 5px 15px rgba(0,0,0,0.15);
        ">
            <h2 style="color:{AlbumRenderer.SPOTIFY_GREEN}; margin-top:0;">
                🎵 {album.title}
            </h2>
            <h4 style="color:#555;">by {album.artist}</h4>

            <a href="{album.uri}" target="_blank">
                <button style="
                    background:{AlbumRenderer.SPOTIFY_GREEN};
                    border:none;
                    padding:12px 22px;
                    font-size:16px;
                    color:white;
                    border-radius:8px;
                    cursor:pointer;
                    margin-bottom:20px;
                ">
                    🎧 Listen on Spotify
                </button>
            </a>

            <div>{html_description}</div>
        </div>
        """))

# Album Recommendation Orchestration Layer
class AlbumRecommendationMCP:
    def __init__(self, csv_path: str = "album_list.csv", selection_type: str = "random"):
        client = genai.Client()
        research_agent = AlbumResearchAgent(client)
        strategy = SelectionFactory.create(selection_type)
        self.agent = AlbumRecommendationAgent(csv_path, research_agent, strategy)

    def execute(self):
        result = self.agent.run()
        AlbumRenderer.render(result)
        return result
```

## **RESULTS:**


```python
# Create Job Spec
prompt = "Create a daily album recommendation using the Album Recommendation MCP."
album_job_specs = natural_language_to_job_specs(prompt)
display_adapter_results(album_job_specs, prompt)

# Run the Job
mcp_job = AlbumRecommendationMCP()
output = mcp_job.execute()
```

    --- ADAPTER RESULTS ---
    
    --- Job #1 ---
    Intent: Create a daily album recommendation using the Album Recommendation MCP.
    Risk Score: 30.0%
    Final Spec Environment: Environment.DEV
    Generated Spec: {
      "name": "daily_album_recommendation",
      "connector": "album_recommendation",
      "schedule": "0 0 * * *",
      "parameters": {},
      "environment": "dev",
      "risk_score_input": [
        "external_egress"
      ],
      "explanation": "Configuring a daily recurring job to fetch and recommend music albums via the Album Recommendation MCP."
    }




        <div style="
            max-width:700px;
            padding:25px;
            border-radius:14px;
            background:#f8f9fa;
            font-family:Arial,sans-serif;
            box-shadow:0 5px 15px rgba(0,0,0,0.15);
        ">
            <h2 style="color:#1DB954; margin-top:0;">
                🎵 Hold The Girl
            </h2>
            <h4 style="color:#555;">by Rina Sawayama</h4>

            <a href="spotify:album:0JO5WJ19NtFRtVYOnw24xS" target="_blank">
                <button style="
                    background:#1DB954;
                    border:none;
                    padding:12px 22px;
                    font-size:16px;
                    color:white;
                    border-radius:8px;
                    cursor:pointer;
                    margin-bottom:20px;
                ">
                    🎧 Listen on Spotify
                </button>
            </a>

            <div><p>Released on September 16, 2022, <strong>"Hold The Girl"</strong> is the second studio album by Japanese-British singer-songwriter Rina Sawayama, centered on the deeply personal theme of healing her "inner child" and processing past trauma. The record serves as an ambitious sonic time capsule, blending diverse genres like pop-rock, country, and UK garage to explore the complexities of identity and forgiveness. It achieved historic commercial success, becoming the highest-charting album by a Japanese-born solo artist in the history of the UK Albums Chart.</p>

<h3><strong>Musical Style and Cultural Significance</strong></h3>

<ul>
<li><strong>Musical Style:</strong> The album is characterized by its "genre-hopping" and maximalist production, masterfully shifting between 2000s-era pop-rock (reminiscent of Kelly Clarkson and Avril Lavigne), Shania Twain-inspired country-pop, and high-energy Eurodance. Critics have described it as a nostalgic yet modern blend of Britpop, industrial rock, and "hyper-pop" sensibilities, often anchored by Sawayama’s powerful, theatrical vocal delivery.</li>
<li><strong>Cultural Significance:</strong> Beyond its record-breaking chart performance (peaking at #3 in the UK), the album holds deep significance for the LGBTQ+ community, particularly through tracks like "This Hell" which serves as a defiant anthem against religious bigotry. It also addresses the Asian diaspora experience, with the opening track "Minor Feelings" referencing Cathy Park Hong’s book on Asian-American marginalization, thereby cementing Sawayama’s role as a vital voice for intersectional identity in mainstream pop.</li>
</ul>

<h3><strong>Sources</strong></h3>

<ol>
<li><strong>Wikipedia:</strong> <a href="https://en.wikipedia.org/wiki/Hold_the_Girl">"Hold the Girl"</a> – Chart records, genre details, and production background.</li>
<li><strong>Beats Per Minute:</strong> <a href="https://beatsperminute.com/album-review-rina-sawayama-hold-the-girl/">"Album Review: Rina Sawayama – Hold the Girl"</a> – Thematic analysis and 90s/00s influences.</li>
<li><strong>The Boar:</strong> <a href="https://theboar.org/2022/10/hold-the-girl-rina-sawayama/">"Hold the Girl: the Unrivalled Power of Rina Sawayama's latest album"</a> – Context on lyrical honesty and genre-hopping.</li>
<li><strong>Mace &amp; Crown:</strong> <a href="https://maceandcrown.com/2022/10/14/rina-sawayamas-hold-the-girl-is-a-love-letter-to-her-inner-child/">"Rina Sawayama's 'Hold the Girl' is a Love Letter to Her Inner Child"</a> – Deep dive into LGBTQ+ themes and specific musical references.</li>
</ol>
</div>
        </div>




```python
# Create Job Spec
prompt = "Create a daily album recommendation using the Album Recommendation MCP."
album_job_specs = natural_language_to_job_specs(prompt)
display_adapter_results(album_job_specs, prompt)

# Run the Job
mcp_job = AlbumRecommendationMCP()
output = mcp_job.execute()
```

    --- ADAPTER RESULTS ---
    
    --- Job #1 ---
    Intent: Create a daily album recommendation using the Album Recommendation MCP.
    Risk Score: 30.0%
    Final Spec Environment: Environment.DEV
    Generated Spec: {
      "name": "daily_album_recommendation_job",
      "connector": "album_recommendation",
      "schedule": "0 9 * * *",
      "parameters": {},
      "environment": "dev",
      "risk_score_input": [
        "external_egress"
      ],
      "explanation": "Automated daily recommendation job utilizing the Album Recommendation MCP."
    }




        <div style="
            max-width:700px;
            padding:25px;
            border-radius:14px;
            background:#f8f9fa;
            font-family:Arial,sans-serif;
            box-shadow:0 5px 15px rgba(0,0,0,0.15);
        ">
            <h2 style="color:#1DB954; margin-top:0;">
                🎵 Thriller
            </h2>
            <h4 style="color:#555;">by Michael Jackson</h4>

            <a href="spotify:album:2ANVost0y2y52ema1E9xAZ" target="_blank">
                <button style="
                    background:#1DB954;
                    border:none;
                    padding:12px 22px;
                    font-size:16px;
                    color:white;
                    border-radius:8px;
                    cursor:pointer;
                    margin-bottom:20px;
                ">
                    🎧 Listen on Spotify
                </button>
            </a>

            <div><p>Released in 1982 and produced by Quincy Jones, Michael Jackson's <em>Thriller</em> remains the best-selling album of all time, famously producing seven top-ten singles and winning a record-breaking eight Grammy Awards. The album’s musical style is a sophisticated fusion of pop, R&amp;B, post-disco, rock, and funk, meticulously crafted to defy traditional genre boundaries and appeal to a universal audience. Culturally, <em>Thriller</em> was a transformative landmark that shattered racial barriers in mainstream media through Michael Jackson’s heavy rotation on MTV and revolutionized the industry by turning music videos into cinematic art forms.</p>

<h3><strong>Musical Style</strong></h3>

<p><em>Thriller</em> is characterized by its "genre-blending" approach, moving away from the disco era to embrace a mix of rock (highlighted by Eddie Van Halen’s solo on "Beat It"), funk, and polished R&amp;B. Its production is noted for a balance of traditional instrumentation and electronic innovation, covering themes ranging from romance to paranoia.</p>

<h3><strong>Cultural Significance</strong></h3>

<p>The album’s success led to "Michaelmania" and established Jackson as a global icon, effectively ending the segregation of Black artists on major television networks like MTV. Its 14-minute title track video redefined the music video format as a narrative short film, setting a new standard for artist branding and visual storytelling.</p>

<h3><strong>Sources</strong></h3>

<ul>
<li><strong>Library of Congress:</strong> Joe Vogel's essay on <em>Thriller</em>'s entry into the National Recording Registry.</li>
<li><strong>Wikipedia:</strong> "Thriller (album)" – Sales data, genre details, and award records.</li>
<li><strong>The Washington Informer:</strong> "Michael Jackson's Thriller: A Legacy That Continues to Dominate Music and Culture."</li>
<li><strong>EBSCO Research Starters:</strong> "Thriller Marks Jackson’s Musical Coming-of-Age."</li>
</ul>
</div>
        </div>




```python
# Create Job Spec
prompt = "Create a daily album recommendation using the Album Recommendation MCP."
album_job_specs = natural_language_to_job_specs(prompt)
display_adapter_results(album_job_specs, prompt)

# Run the Job
mcp_job = AlbumRecommendationMCP()
output = mcp_job.execute()
```

    --- ADAPTER RESULTS ---
    
    --- Job #1 ---
    Intent: Create a daily album recommendation using the Album Recommendation MCP.
    Risk Score: 0.0%
    Final Spec Environment: Environment.DEV
    Generated Spec: {
      "name": "daily_album_recommendation",
      "connector": "album-recommendation",
      "schedule": "0 0 * * *",
      "parameters": {},
      "environment": "dev",
      "risk_score_input": [],
      "explanation": "Daily album recommendation job based on user request."
    }




        <div style="
            max-width:700px;
            padding:25px;
            border-radius:14px;
            background:#f8f9fa;
            font-family:Arial,sans-serif;
            box-shadow:0 5px 15px rgba(0,0,0,0.15);
        ">
            <h2 style="color:#1DB954; margin-top:0;">
                🎵 IT'S TOO QUIET..!!
            </h2>
            <h4 style="color:#555;">by Pink Siifu & Turich Benjy</h4>

            <a href="No URI Found" target="_blank">
                <button style="
                    background:#1DB954;
                    border:none;
                    padding:12px 22px;
                    font-size:16px;
                    color:white;
                    border-radius:8px;
                    cursor:pointer;
                    margin-bottom:20px;
                ">
                    🎧 Listen on Spotify
                </button>
            </a>

            <div><p>Released on October 31, 2023, <em>IT'S TOO QUIET..!!</em> is a collaborative project between Cincinnati-raised artists Pink Siifu and Turich Benjy that features 17 tracks and production from industry staples like Harry Fraud and Tony Seltzer. The album serves as an expansive, genre-defying follow-up to their previous collaborations on Siifu’s <em>GUMBO'!</em>, showcasing a high-energy "absurdist take" on contemporary rap and electronic sounds. By merging underground aesthetics with diverse regional influences, the project cements the duo's position as boundary-pushing figures in the modern independent landscape.</p>

<h3><strong>Musical Style and Cultural Significance</strong></h3>

<ul>
<li><strong>Musical Style:</strong> The album is a "genre-contorting" mosaic that blends <strong>underground hip-hop</strong> and <strong>alternative trap</strong> with elements of <strong>Ghettotech</strong>, <strong>techno</strong>, <strong>house</strong>, and <strong>neo-soul</strong>. It ranges from hazy "cloud rap" and soulful R&amp;B moments to abrasive, high-tempo electronic experiments, often utilizing auto-tuned vocals and "unquantized" instrumentation to create an immersive, unpredictable listening experience.</li>
<li><strong>Cultural Significance:</strong> Centered on the <strong>Cincinnati contemporary scene</strong>, the album highlights the creative synergy of the <strong>GKFAM collective</strong> and pays homage to Southern hip-hop legacies, specifically the <strong>Dungeon Family</strong> (evident through the narration of Big Rube). It is celebrated for its <strong>independent spirit</strong>, rejecting algorithm-driven trends in favor of a "genre-agnostic" approach that prioritizes artistic obsession and collaborative community over mainstream commerciality.</li>
</ul>

<h3><strong>Sources</strong></h3>

<ul>
<li><strong>Lyrical Lemonade:</strong> Details on the Cincinnati scene and genre-contorting production.</li>
<li><strong>In Search of Media:</strong> Information on the October 31 release date and electronic/trap influences.</li>
<li><strong>Stereogum:</strong> Coverage of the collaborative history between Siifu and Benjy.</li>
<li><strong>Passion of the Weiss:</strong> Insight into the album’s "genre-agnostic" philosophy and cultural roots.</li>
<li><strong>Hypebeast:</strong> Overview of the tracklist and featured artists like Nick Hakim and WiFiGawd.</li>
</ul>
</div>
        </div>


