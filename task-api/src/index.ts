import { env } from './config/env.js';
import { getDatabaseManager, closeDatabaseManager } from './config/database.js';
import { createApp } from './app.js';

async function main() {
  // Initialize database
  console.log('Initializing database...');
  await getDatabaseManager();
  console.log('Database initialized');

  // Create and start server
  const app = createApp();
  const server = app.listen(env.PORT, () => {
    console.log(`Server running on port ${env.PORT}`);
    console.log(`API available at http://localhost:${env.PORT}/api/v1`);
  });

  // Graceful shutdown
  const shutdown = async (signal: string) => {
    console.log(`\n${signal} received. Shutting down gracefully...`);
    server.close(async () => {
      await closeDatabaseManager();
      console.log('Server closed');
      process.exit(0);
    });
  };

  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT', () => shutdown('SIGINT'));
}

main().catch((error) => {
  console.error('Failed to start server:', error);
  process.exit(1);
});
