"""
Error Log Pipeline - Sends errors from Dummy Service to AutoSRE AI
This simulates real-world incident flow
"""
import requests
import json
import time
import argparse
from datetime import datetime

class ErrorPipeline:
    """Pipeline that sends errors from dummy service to AutoSRE AI"""
    
    def __init__(self, dummy_service_url: str, autosre_url: str):
        """
        Args:
            dummy_service_url: URL of dummy service (e.g., http://localhost:8001)
            autosre_url: URL of AutoSRE AI service (e.g., http://localhost:8000)
        """
        self.dummy_url = dummy_service_url.rstrip("/")
        self.autosre_url = autosre_url.rstrip("/")
    
    def get_error_from_dummy_service(self, error_type: str = None) -> dict:
        """
        Get error log from dummy service
        
        Args:
            error_type: Specific error type to generate, or None for random
        
        Returns:
            Error log dict
        """
        if error_type:
            url = f"{self.dummy_url}/generate-error/{error_type}"
        else:
            url = f"{self.dummy_url}/generate-error"
        
        try:
            print(f"[→] Fetching error from dummy service: {url}")
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            error_log = response.json()
            print(f"✓ Got error: {error_log.get('error_type', 'UNKNOWN')}")
            return error_log
        except Exception as e:
            print(f"✗ Error fetching from dummy service: {e}")
            return None
    
    def send_to_autosre(self, error_log: dict) -> dict:
        """
        Send error log to AutoSRE AI for processing
        
        Args:
            error_log: Error log dict
        
        Returns:
            Analysis result
        """
        url = f"{self.autosre_url}/analyze"
        
        # Convert error dict to formatted string
        log_string = json.dumps(error_log, indent=2)
        
        payload = {
            "log": log_string
        }
        
        try:
            print(f"\n[→] Sending to AutoSRE AI: {url}")
            print(f"    Payload: {len(log_string)} bytes")
            
            response = requests.post(
                url,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            
            print(f"✓ Got analysis result")
            return result
        except Exception as e:
            print(f"✗ Error sending to AutoSRE: {e}")
            return None
    
    def process_error(self, error_type: str = None) -> dict:
        """
        Complete pipeline: Dummy Service → Error → AutoSRE AI → Decision
        
        Args:
            error_type: Optional specific error type
        
        Returns:
            Complete result with analysis and decision
        """
        print("\n" + "=" * 80)
        print("ERROR PROCESSING PIPELINE")
        print("=" * 80)
        
        # Step 1: Get error from dummy service
        error_log = self.get_error_from_dummy_service(error_type)
        if not error_log:
            return {"success": False, "error": "Failed to get error from dummy service"}
        
        # Step 2: Send to AutoSRE for processing
        result = self.send_to_autosre(error_log)
        if not result:
            return {"success": False, "error": "Failed to send to AutoSRE"}
        
        # Step 3: Display results
        self._display_results(error_log, result)
        
        return {
            "success": True,
            "error_log": error_log,
            "analysis_result": result
        }
    
    def _display_results(self, error_log: dict, result: dict):
        """Display processing results in readable format"""
        
        print("\n" + "-" * 80)
        print("ANALYSIS RESULTS")
        print("-" * 80)
        
        if result.get("success"):
            analysis = result.get("analysis", {})
            rag = result.get("rag", {})
            decision = result.get("decision", {})
            execution = result.get("execution", {})
            
            print(f"\n📊 ERROR ANALYSIS:")
            print(f"   Error Type: {analysis.get('error_type', 'N/A')}")
            print(f"   Severity: {analysis.get('severity', 'N/A')}")
            print(f"   Root Cause: {analysis.get('root_cause', 'N/A')}")
            print(f"   Affected Services: {', '.join(analysis.get('services_affected', []))}")
            
            print(f"\n🔍 KNOWLEDGE BASE (RAG):")
            print(f"   Found Match: {rag.get('found', False)}")
            print(f"   Confidence: {rag.get('confidence', 0):.2%}")
            print(f"   Solutions Count: {rag.get('solutions_count', 0)}")
            
            print(f"\n🎯 DECISION:")
            print(f"   Action: {decision.get('action', 'N/A')}")
            print(f"   Reasoning: {decision.get('reasoning', 'N/A')}")
            print(f"   Confidence: {decision.get('confidence', 0):.2%}")
            
            print(f"\n⚙️  EXECUTION:")
            print(f"   Success: {execution.get('success', False)}")
            
            tools_executed = execution.get('tools_executed', [])
            if tools_executed:
                print(f"   Tools Executed:")
                for tool in tools_executed:
                    tool_name = tool.get('tool', 'unknown')
                    is_success = tool.get('result', {}).get('success', False)
                    status = "✓" if is_success else "✗"
                    print(f"     {status} {tool_name}")
        else:
            print(f"\n✗ Analysis failed: {result.get('error', 'Unknown error')}")
        
        print("\n" + "=" * 80)
    
    def run_continuous(self, interval: int = 30, error_type: str = None):
        """
        Run continuous error simulation
        
        Args:
            interval: Seconds between error generations
            error_type: Optional specific error type
        """
        print(f"\n[*] Starting continuous error simulation (interval: {interval}s)")
        print(f"[*] Press Ctrl+C to stop\n")
        
        iteration = 1
        try:
            while True:
                print(f"\n[ITERATION {iteration}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                self.process_error(error_type)
                
                if iteration < 1000:  # Reasonable iteration limit
                    print(f"[*] Next error in {interval} seconds...")
                    time.sleep(interval)
                else:
                    print("[*] Reached iteration limit")
                    break
                
                iteration += 1
        except KeyboardInterrupt:
            print("\n\n[*] Stopped")


def main():
    parser = argparse.ArgumentParser(
        description="Error Log Pipeline: Dummy Service → AutoSRE AI"
    )
    parser.add_argument(
        "--dummy-url",
        default="http://localhost:8001",
        help="Dummy service URL (default: http://localhost:8001)"
    )
    parser.add_argument(
        "--autosre-url",
        default="http://localhost:8000",
        help="AutoSRE AI service URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--error-type",
        help="Specific error type to generate (if not specified, generates random)"
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Run continuous simulation"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Interval between errors in continuous mode (default: 30s)"
    )
    parser.add_argument(
        "--list-errors",
        action="store_true",
        help="List available error types"
    )
    
    args = parser.parse_args()
    
    pipeline = ErrorPipeline(args.dummy_url, args.autosre_url)
    
    # List available errors if requested
    if args.list_errors:
        try:
            response = requests.get(f"{args.dummy_url}/errors", timeout=5)
            errors = response.json()
            print("\nAvailable Error Types:")
            for error in errors.get("available_errors", []):
                print(f"  - {error}")
            print()
        except Exception as e:
            print(f"Error fetching error types: {e}")
        return
    
    # Run continuous or single processing
    if args.continuous:
        pipeline.run_continuous(args.interval, args.error_type)
    else:
        pipeline.process_error(args.error_type)


if __name__ == "__main__":
    main()
