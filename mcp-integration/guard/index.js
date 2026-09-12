import { decide } from './policy.js';

export default {
  id: 'vinceai-mcp-guard',
  name: 'Sanctum MCP Guard',
  register(api) {
    api.on('before_tool_call', event => decide(event), {priority: 1000});
  },
};
