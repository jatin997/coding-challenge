import json
import requests
import argparse
import sys
from urllib.parse import urljoin

class AWSMetadataClient:
    """Client for querying AWS EC2 instance metadata service."""
    
    def __init__(self):
        self.base_url = "http://169.254.169.254/latest/meta-data/"
        self.token_url = "http://169.254.169.254/latest/api/token"
        self.session = requests.Session()
        self.token = None
        
    def _get_token(self):
        """Get IMDSv2 token for secure metadata access."""
        try:
            headers = {'X-aws-ec2-metadata-token-ttl-seconds': '21600'}
            response = self.session.put(self.token_url, headers=headers, timeout=5)
            response.raise_for_status()
            self.token = response.text
            return True
        except requests.RequestException as e:
            print(f"Warning: Could not get IMDSv2 token, falling back to IMDSv1: {e}")
            return False
    
    def _make_request(self, path):
        """Make a request to the metadata service."""
        url = urljoin(self.base_url, path)
        headers = {}
        
        if self.token:
            headers['X-aws-ec2-metadata-token'] = self.token
            
        try:
            response = self.session.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            raise Exception(f"Failed to retrieve metadata from {path}: {e}")
    
    def _is_directory(self, path):
        """Check if a path is a directory by looking for trailing slash in response."""
        try:
            content = self._make_request(path)
            return content.endswith('/')
        except:
            return False
    
    def _get_metadata_recursive(self, path=""):
        """Recursively retrieve metadata structure."""
        try:
            content = self._make_request(path)
            lines = content.strip().split('\n')
            
            result = {}
            for line in lines:
                if not line:
                    continue
                    
                item_path = f"{path}{line}" if path else line
                
                if line.endswith('/'):
                    # Directory - recurse
                    key = line[:-1]  # Remove trailing slash
                    result[key] = self._get_metadata_recursive(item_path)
                else:
                    # File - get value
                    try:
                        value = self._make_request(item_path)
                        result[line] = value
                    except Exception as e:
                        result[line] = f"Error: {str(e)}"
                        
            return result
            
        except Exception as e:
            return f"Error retrieving {path}: {str(e)}"
    
    def get_all_metadata(self):
        """Get all available metadata."""
        if not self.token:
            self._get_token()
            
        return self._get_metadata_recursive()
    
    def get_specific_key(self, key_path):
        """Get a specific metadata key."""
        if not self.token:
            self._get_token()
            
        try:
            # Handle nested keys (e.g., "placement/availability-zone")
            value = self._make_request(key_path)
            return {key_path: value}
        except Exception as e:
            return {"error": f"Could not retrieve key '{key_path}': {str(e)}"}

def main():
    parser = argparse.ArgumentParser(
        description="Query AWS EC2 instance metadata and return JSON output",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python metadata_query.py                           # Get all metadata
  python metadata_query.py --key instance-id        # Get specific key
  python metadata_query.py --key placement/availability-zone  # Get nested key
  python metadata_query.py --pretty                 # Pretty print JSON
        """
    )
    
    parser.add_argument(
        '--key', '-k',
        help='Retrieve a specific metadata key (e.g., instance-id, placement/availability-zone)'
    )
    
    parser.add_argument(
        '--pretty', '-p',
        action='store_true',
        help='Pretty print JSON output'
    )
    
    parser.add_argument(
        '--list-keys',
        action='store_true',
        help='List available metadata keys'
    )
    
    args = parser.parse_args()
    
    try:
        client = AWSMetadataClient()
        
        if args.list_keys:
            # Just get top-level keys for listing
            content = client._make_request("")
            keys = [line.rstrip('/') for line in content.strip().split('\n')]
            result = {"available_keys": keys}
        elif args.key:
            result = client.get_specific_key(args.key)
        else:
            result = client.get_all_metadata()
        
        # Output JSON
        if args.pretty:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(json.dumps(result, sort_keys=True))
            
    except Exception as e:
        error_result = {"error": str(e)}
        if args.pretty:
            print(json.dumps(error_result, indent=2))
        else:
            print(json.dumps(error_result))
        sys.exit(1)

if __name__ == "__main__":
    main()
