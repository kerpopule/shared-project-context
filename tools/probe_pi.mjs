// Exercise Pi's shipped MCP runtime, without starting a model session.
// Usage: node tools/probe_pi.mjs PI_PACKAGE_ROOT INSTALLED_LAUNCHER PROJECT
import assert from 'node:assert/strict';
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';
const [root, launcher, project] = process.argv.slice(2);
if (!root || !launcher || !project) throw new Error('package_root_launcher_and_project_required');
const {McpServerConnection, createDefaultTransport, McpOAuthCredentialStore} = await import(
  pathToFileURL(join(root, 'dist/extensions/mcp/runtime.js')).href);
const connection = new McpServerConnection({
  entry: {name: 'shared-project-context', config: {command: launcher, args: ['serve', '--project', project]}, source: 'isolated-probe', scope: 'extension'},
  cwd: process.cwd(), createTransport: createDefaultTransport,
  credentials: new McpOAuthCredentialStore(), onTools: () => {},
});
try {
  await connection.getClient();
  assert.equal(connection.state, 'connected');
  assert.equal(connection.tools.length, 6); // Scope hides register and reference mutation.
  const call = async (name, args) => {
    const result = await connection.callTool(name, args, {timeoutMs: 10000});
    assert.notEqual(result.isError, true, JSON.stringify(result));
    return JSON.parse(result.content[0].text);
  };
  const before = await call('project_context', {project});
  assert.equal(before.decisions[0].text, 'Manual exports only');
  await call('project_begin', {project, actor: 'pi-native', session: 'native-fixture'});
  const event = await call('project_checkpoint', {
    project, actor: 'pi-native', session: 'native-fixture', expected_revision: before.revision,
    key: 'pi-native-result', status: 'proposed', summary: 'Reviewed the shared export decision',
  });
  assert.equal(event.revision, before.revision + 1);
  await call('project_finish', {project, actor: 'pi-native', session: 'native-fixture'});
  const denied = await connection.callTool('project_context', {project: 'not-granted'}, {timeoutMs: 10000});
  assert.equal(denied.isError, true);
  const resources = await connection.allResources({timeoutMs: 10000});
  assert.equal(resources.length, 1);
  console.log(JSON.stringify({runtime: 'Pi shipped McpServerConnection',
    connected: true, tool_count: connection.tools.length, decision_recalled: true,
    checkpoint_written: true, ungranted_project_denied: true, resources_discovered: true,
    model_inference_exercised: false}));
} finally {
  await connection.close();
}
