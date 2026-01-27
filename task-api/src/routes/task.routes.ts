import { Router } from 'express';
import { taskController } from '../controllers/task.controller.js';
import { validate } from '../middleware/validate.js';
import { CreateTaskSchema, UpdateTaskSchema, PatchTaskSchema, TaskQuerySchema } from '../schemas/task.schema.js';

const router = Router();

router.get('/', validate(TaskQuerySchema, 'query'), taskController.getAll);
router.get('/:id', taskController.getById);
router.post('/', validate(CreateTaskSchema, 'body'), taskController.create);
router.put('/:id', validate(UpdateTaskSchema, 'body'), taskController.update);
router.patch('/:id', validate(PatchTaskSchema, 'body'), taskController.patch);
router.delete('/:id', taskController.delete);

export { router as taskRoutes };
