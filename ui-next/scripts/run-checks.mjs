#!/usr/bin/env node
import { spawn } from 'node:child_process';

const npmCmd = process.platform === 'win32' ? 'npm.cmd' : 'npm';
const npxCmd = process.platform === 'win32' ? 'npx.cmd' : 'npx';

const tasks = [
  { title: 'Lint', command: npmCmd, args: ['run', 'lint'] },
  { title: 'Type check', command: npxCmd, args: ['tsc', '--noEmit'] },
  { title: 'Build', command: npmCmd, args: ['run', 'build'] }
];

async function runTask({ title, command, args }) {
  console.log(`\n==> ${title}`);
  console.log(`$ ${[command, ...args].join(' ')}`);
  return await new Promise(resolve => {
    const child = spawn(command, args, { stdio: 'inherit', shell: false });
    child.on('close', code => {
      const status = code === 0 ? 'OK' : `FALLO (${code})`;
      console.log(`-- Resultado: ${status}`);
      resolve({ title, code });
    });
  });
}

(async () => {
  const results = [];
  for (const task of tasks) {
    results.push(await runTask(task));
  }

  console.log('\nResumen de comprobaciones:');
  for (const result of results) {
    const status = result.code === 0 ? '✔' : '✖';
    console.log(`  ${status} ${result.title}`);
  }

  const failed = results.filter(result => result.code !== 0);
  if (failed.length > 0) {
    console.log('\nSe detectaron fallos en las comprobaciones anteriores.');
    process.exit(1);
  }
})();
