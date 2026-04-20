const fs = require('fs');
const html = fs.readFileSync('index.html', 'utf-8');
// Extract all <script> blocks (not src-linked ones)
const matches = html.match(/<script>[\s\S]*?<\/script>/g) || [];
const src = matches
  .map(s => s.replace(/^<script>/, '').replace(/<\/script>$/, ''))
  .join('\n');
try {
  new Function(src);
  console.log('✅ JS syntax OK — no errors found');
} catch(e) {
  console.error('❌ JS syntax error:', e.message);
  // Show surrounding lines
  const lines = src.split('\n');
  const lineNum = parseInt((e.stack.match(/<anonymous>:(\d+)/) || [])[1]) || 0;
  const start = Math.max(0, lineNum - 3);
  const end = Math.min(lines.length, lineNum + 3);
  lines.slice(start, end).forEach((l, i) => {
    const num = start + i + 1;
    console.error(`${num === lineNum ? '>>>' : '   '} ${num}: ${l}`);
  });
  process.exit(1);
}
