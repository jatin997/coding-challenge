# coding-challenge

Here's a Python implementation that queries the metadata of a cloud instance (e.g., AWS EC2 or Azure VM) and allows retrieval of a specific metadata key. This example uses the AWS EC2 Instance Metadata Service (IMDSv2), but it can be adapted for other cloud providers.

🛠️ How It Works
•	Uses IMDSv2 for secure metadata access.
•	If no key is provided, it fetches all available metadata keys and their values.
•	If a specific key is passed (e.g., --key hostname), it returns only that key.
•	Outputs the result in JSON format.
