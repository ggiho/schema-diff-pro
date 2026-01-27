import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import { apiRoutes } from './routes/index.js';
import { errorHandler } from './middleware/error-handler.js';
import { AppError } from './middleware/errors.js';

export function createApp() {
  const app = express();

  // Security middleware
  app.use(helmet());
  app.use(cors());

  // Body parsing
  app.use(express.json());

  // API routes
  app.use('/api/v1', apiRoutes);

  // Health check
  app.get('/health', (req, res) => {
    res.json({ status: 'ok' });
  });

  // 404 handler
  app.use((req, res, next) => {
    next(new AppError(404, `Route ${req.method} ${req.path} not found`, 'ROUTE_NOT_FOUND'));
  });

  // Global error handler
  app.use(errorHandler);

  return app;
}
