import dataclasses
import warnings
from flask import Flask, jsonify, request
from flask_cors import CORS

# Suppress benign google.genai SDK warning about AFC in generate_content
warnings.filterwarnings("ignore", message=".*Direct use of automatic function calling.*")

from pipelines.runner import get_available_pipelines, run_pipeline

app = Flask(__name__)
CORS(app)

@app.route('/api/pipelines', methods=['GET'])
def list_pipelines():
    """
    Returns a list of all available job pipelines.
    """
    pipelines = get_available_pipelines()
    return jsonify({
        "status": "success",
        "data": pipelines
    })

@app.route('/api/pipelines/<pipeline_name>/run', methods=['POST'])
def trigger_pipeline(pipeline_name):
    """
    Triggers a specific pipeline and returns the result.
    """
    pipelines = [p['code'] for p in get_available_pipelines()]
    
    if pipeline_name not in pipelines:
        return jsonify({
            "status": "error",
            "message": f"Pipeline '{pipeline_name}' not found. Available pipelines: {pipelines}"
        }), 404

    # Run the pipeline synchronously
    result = run_pipeline(pipeline_name)
    
    return jsonify({
        "status": "success",
        "data": dataclasses.asdict(result)
    })

@app.route('/api/discovery/run', methods=['POST'])
def trigger_company_discovery():
    """
    Runs multi-platform ATS discovery across Indian tech companies.
    Optional JSON body: {"limit": 30, "workers": 8}
    """
    from tools.company_discovery import CompanyDiscoveryEngine
    from tools.indian_company_list import INDIAN_COMPANIES

    body = request.get_json(silent=True) or {}
    limit = body.get('limit', 50)
    offset = body.get('offset', 0)
    workers = body.get('workers', 8)
    auto_add = body.get('auto_add', False)

    sample = INDIAN_COMPANIES[offset:offset+limit] if limit else INDIAN_COMPANIES[offset:]
    engine = CompanyDiscoveryEngine()
    discovered = engine.run_discovery(sample, max_workers=workers, auto_add=auto_add)

    return jsonify({
        "status": "success",
        "total_probed": len(sample),
        "data": discovered
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
