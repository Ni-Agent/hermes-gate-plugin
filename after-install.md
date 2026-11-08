# Connect to your Gate

Enter the **Gate URL** and dedicated **Hermes agent token** supplied by the Gate
operator. The token is not your ChatGPT OAuth login password.

1. Run `hermes gate status` to verify the connection and identity.
2. Ask Hermes to read `/kb/projects/gate`.
3. From your chosen work directory, run `hermes gate listen` to enable outbound SSE
   task pickup. Plugin loading alone does not start workers.
4. For persistence: `hermes gate install-service`, review the printed user unit,
   then enable it as instructed. See README.md for crash recovery and safeguards.

Do not run the earlier experimental MCP/skill setup script for this plugin.
