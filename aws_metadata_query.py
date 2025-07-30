#!/usr/bin/env python3
"""
AWS EC2 Instance Metadata Query Tool

This script queries AWS EC2 instance metadata service and provides:
1. Complete metadata in JSON format
2. Individual key retrieval functionality
3. Error handling for network issues and invalid keys

Usage:
    python metadata_query.py                    # Get all metadata as JSON
    python metadata_query.py --key instance-id  # Get specific key
    python metadata_query.py --list            # List available keys
"""

import requests
import json
import argparse
import sys
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin

class AWSMetadataClient:
    """Client for querying AWS EC2 Instance Metadata Service (IMDS)"""
    
    def __init__(self, timeout: int = 5):
        self.base_url = "http://169.254.169.254/latest/meta-data/"
        self.timeout = timeout
        self.session = requests.Session()
        
        # Get IMDSv2 token for secure access
        self.token = self._get_imds_token()
        if self.token:
            self.session.headers.update({'X-aws-ec2-metadata-token': self.token})
    
    def _get_imds_token(self) -> Optional[str]:
        """Get IMDSv2 token for secure metadata access"""
        try:
            token_url = "http://169.254.169.254/latest/api/token"
            headers = {'X-aws-ec2-metadata-token-ttl-seconds': '21600'}
            response = self.session.put(token_url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Warning: Could not get IMDSv2 token, falling back to IMDSv1: {e}")
            return None
    
    def _make_request(self, endpoint: str) -> Optional[str]:
        """Make a request to the metadata service"""
        try:
            url = urljoin(self.base_url, endpoint)
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error querying {endpoint}: {e}")
            return None
    
    def _is_directory(self, endpoint: str) -> bool:
        """Check if an endpoint returns a directory listing"""
        content = self._make_request(endpoint)
        return content is not None and content.endswith('/')
    
    def _parse_directory(self, content: str) -> List[str]:
        """Parse directory listing from metadata response"""
        return [line.rstrip('/') for line in content.strip().split('\n') if line]
    
    def _get_nested_metadata(self, endpoint: str = "") -> Dict[str, Any]:
        """Recursively get all metadata from a given endpoint"""
        content = self._make_request(endpoint)
        if content is None:
            return {}
        
        # If content ends with '/', it's a directory listing
        if content.endswith('/') or '\n' in content:
            result = {}
            items = self._parse_directory(content)
            
            for item in items:
                item_endpoint = f"{endpoint}{item}/" if endpoint else f"{item}/"
                item_content = self._make_request(item_endpoint.rstrip('/'))
                
                if item_content and (item_content.endswith('/') or '\n' in item_content):
                    # It's a subdirectory
                    result[item] = self._get_nested_metadata(item_endpoint)
                else:
                    # It's a value
                    result[item] = item_content
            
            return result
        else:
            # It's a single value
            return content
    
    def get_all_metadata(self) -> Dict[str, Any]:
        """Get all available metadata as a nested dictionary"""
        try:
            metadata = self._get_nested_metadata()
            return metadata
        except Exception as e:
            print(f"Error retrieving metadata: {e}")
            return {}
    
    def get_metadata_key(self, key: str) -> Optional[str]:
        """Get a specific metadata key value"""
        # Handle nested keys (e.g., 'placement/availability-zone')
        key_path = key.replace('.', '/').replace('_', '-')
        return self._make_request(key_path)
    
    def list_available_keys(self) -> List[str]:
        """List all available metadata keys"""
        def collect_keys(data: Dict[str, Any], prefix: str = "") -> List[str]:
            keys = []
            for key, value in data.items():
                full_key = f"{prefix}/{key}" if prefix else key
                if isinstance(value, dict):
                    keys.extend(collect_keys(value, full_key))
                else:
                    keys.append(full_key)
            return keys
        
        metadata = self.get_all_metadata()
        return collect_keys(metadata)

def main():
    parser = argparse.ArgumentParser(
        description='Query AWS EC2 Instance Metadata',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Get all metadata as JSON
  %(prog)s --key instance-id         # Get instance ID
  %(prog)s --key placement/availability-zone  # Get AZ
  %(prog)s --list                    # List all available keys
  %(prog)s --key ami-id --format raw # Get AMI ID without JSON formatting
        """
    )
    
    parser.add_argument(
        '--key', '-k',
        help='Specific metadata key to retrieve'
    )
    
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List all available metadata keys'
    )
    
    parser.add_argument(
        '--format', '-f',
        choices=['json', 'raw'],
        default='json',
        help='Output format (default: json)'
    )
    
    parser.add_argument(
        '--timeout', '-t',
        type=int,
        default=5,
        help='Request timeout in seconds (default: 5)'
    )
    
    parser.add_argument(
        '--pretty',
        action='store_true',
        help='Pretty-print JSON output'
    )
    
    args = parser.parse_args()
    
    # Initialize metadata client
    client = AWSMetadataClient(timeout=args.timeout)
    
    try:
        if args.list:
            # List all available keys
            keys = client.list_available_keys()
            if keys:
                print("Available metadata keys:")
                for key in sorted(keys):
                    print(f"  {key}")
            else:
                print("No metadata keys found or unable to connect to metadata service")
                sys.exit(1)
        
        elif args.key:
            # Get specific key
            value = client.get_metadata_key(args.key)
            if value is not None:
                if args.format == 'raw':
                    print(value)
                else:
                    output = {args.key: value}
                    if args.pretty:
                        print(json.dumps(output, indent=2))
                    else:
                        print(json.dumps(output))
            else:
                print(f"Key '{args.key}' not found or inaccessible")
                sys.exit(1)
        
        else:
            # Get all metadata
            metadata = client.get_all_metadata()
            if metadata:
                if args.pretty:
                    print(json.dumps(metadata, indent=2))
                else:
                    print(json.dumps(metadata))
            else:
                print("No metadata found or unable to connect to metadata service")
                sys.exit(1)
    
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
