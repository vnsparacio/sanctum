// The model relay may shape requests, but it cannot authorize tools or work.
const COMPACTION_PREFIX = 'You are the component that summarizes a conversation when its context window is about to overflow.';
const ANALYSIS_START = 'First, wrap your reasoning in an <analysis> block.';
const SUMMARY_START = 'Then produce the final summary as the EXACT XML structure below.';

function textOnlySummaryPrompt(content) {
  const first = content.indexOf(ANALYSIS_START);
  const last = content.indexOf(SUMMARY_START);
  if (first < 0 || last < first) throw Error('qwen_compaction_template');
  return content.slice(0, first) +
    'Produce only the final <state_snapshot> XML. Do not write an analysis block, reasoning preamble, or tool call. Keep the summary concise and preserve the active task, changed files, test failures, and next step.\n' +
    content.slice(last);
}

export function prepareQwenRequest(value, model) {
  if (value?.model !== model || !Array.isArray(value.messages)) throw Error('qwen_model_identity');
  const system = value.messages[0];
  const compaction = system?.role === 'system' &&
    typeof system.content === 'string' && system.content.startsWith(COMPACTION_PREFIX);
  const request = {
    ...value,
    max_tokens: compaction ? 6144 : 4096,
    temperature: 0.7,
    top_p: 0.8,
    top_k: 20,
    min_p: 0,
    presence_penalty: 1.5,
    repetition_penalty: 1,
    chat_template_kwargs: { enable_thinking: false },
    stream_options: { include_usage: true },
  };
  if (compaction) {
    // Qwen Code 0.24.6 requests a long analysis draft before the actual
    // summary. The private model exhausted that draft and later returned a
    // tool call despite receiving no tool schemas. Keep the XML contract.
    request.messages = [{...system, content: textOnlySummaryPrompt(system.content)}, ...value.messages.slice(1)];
    delete request.tools;
    request.tool_choice = 'none';
    delete request.parallel_tool_calls;
    request.temperature = 0.2;
  }
  return request;
}
