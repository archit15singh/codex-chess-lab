// Stateless vision calls keep playing and verification contexts separate.
const instructions = 'You are a chess computer-use agent. Interpret pixels and follow the supplied JSON contract.';
const endpoints = {
  anthropic: 'https://api.anthropic.com/v1/messages',
  openai: 'https://api.openai.com/v1/responses',
};

export function visionAgent({ provider, model }, apiKey, request = fetch) {
  if (!apiKey?.trim()) throw new Error(`Missing ${provider} API key`);
  return async (prompt, images) => {
    const claude = provider === 'anthropic';
    const base64 = images.map(image => image.toString('base64'));
    const headers = claude
      ? { 'x-api-key': apiKey, 'anthropic-version': '2023-06-01' }
      : { authorization: `Bearer ${apiKey}` };
    const body = claude ? {
      model, max_tokens: 2048, system: instructions,
      messages: [{ role: 'user', content: [
        ...base64.map(data => ({ type: 'image', source: { type: 'base64', media_type: 'image/png', data } })),
        { type: 'text', text: prompt },
      ] }],
    } : {
      model, store: false, max_output_tokens: 4096, instructions,
      text: { format: { type: 'json_object' } },
      input: [{ role: 'user', content: [
        ...base64.map(data => ({ type: 'input_image', detail: 'high', image_url: `data:image/png;base64,${data}` })),
        { type: 'input_text', text: prompt },
      ] }],
    };
    const response = await request(endpoints[provider], {
      method: 'POST', headers: { ...headers, 'content-type': 'application/json' },
      body: JSON.stringify(body), signal: AbortSignal.timeout(45_000), redirect: 'error',
    });
    if (!response.ok) throw new Error(`${provider} returned HTTP ${response.status}`);
    const payload = await response.json();
    const blocks = claude ? payload.content : payload.output?.flatMap(item => item.content ?? []);
    if ((claude ? payload.stop_reason !== 'end_turn' : payload.status !== 'completed') || !Array.isArray(blocks)) {
      throw new Error(`${provider} did not complete its vision response`);
    }
    const message = blocks.filter(block => block.type === (claude ? 'text' : 'output_text'))
      .map(block => block.text).join('').trim();
    try {
      return JSON.parse(message);
    } catch {
      throw new Error(`${provider} did not return valid JSON`);
    }
  };
}
