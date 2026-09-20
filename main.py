import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description="Job Pipeline Standalone Execution")
    parser.add_argument(
        '--run', 
        type=str, 
        required=False, 
        help="Name of the pipeline to run (e.g. 'ashby', 'greenhouse', or 'user_pipeline')"
    )
    parser.add_argument(
        '--serve', 
        action='store_true',
        help="Start the Flask API server"
    )
    parser.add_argument(
        '--user_id', 
        type=int, 
        help="User ID required only if running the 'user_pipeline'"
    )

    args = parser.parse_args()

    if args.serve:
        from api import app
        print("Starting Flask API server...")
        app.run(host='0.0.0.0', port=5000, debug=True)
    elif args.run == 'user_pipeline':
        if not args.user_id:
            print("ERROR: --user_id is required for the user_pipeline")
            sys.exit(1)
        from pipeline_orchestrator import execute_job_pipeline
        execute_job_pipeline(user_id=args.user_id)
        
    elif args.run:
        # Run standard ATS board pipeline
        try:
            from pipelines.runner import execute_single_pipeline
            success = execute_single_pipeline(args.run)
            if not success:
                print(f"ERROR: Pipeline {args.run} failed.")
                sys.exit(1)
        except ImportError:
            # Fallback to newer runner structure if execute_single_pipeline is not there
            try:
                from pipelines.runner import run_pipeline
                res = run_pipeline(args.run)
                if res.status == 'failed':
                    print(f"ERROR: Pipeline {args.run} failed: {res.error_message}")
                    sys.exit(1)
            except ImportError:
                print("ERROR: Could not import pipeline runner.")
                sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == '__main__':
    main()
