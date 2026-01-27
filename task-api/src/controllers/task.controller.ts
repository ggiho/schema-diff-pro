import { Request, Response, NextFunction } from 'express';
import { taskService } from '../services/task.service.js';
import { CreateTaskDto, UpdateTaskDto, PatchTaskDto, TaskQuery } from '../schemas/task.schema.js';

export const taskController = {
  async getAll(req: Request, res: Response, next: NextFunction) {
    try {
      const query = req.query as TaskQuery;
      const tasks = await taskService.getAllTasks(query);
      res.json({ data: tasks, meta: { total: tasks.length } });
    } catch (error) { next(error); }
  },

  async getById(req: Request, res: Response, next: NextFunction) {
    try {
      const task = await taskService.getTaskById(req.params.id);
      res.json({ data: task });
    } catch (error) { next(error); }
  },

  async create(req: Request, res: Response, next: NextFunction) {
    try {
      const task = await taskService.createTask(req.body as CreateTaskDto);
      res.status(201).json({ data: task });
    } catch (error) { next(error); }
  },

  async update(req: Request, res: Response, next: NextFunction) {
    try {
      const task = await taskService.updateTask(req.params.id, req.body as UpdateTaskDto);
      res.json({ data: task });
    } catch (error) { next(error); }
  },

  async patch(req: Request, res: Response, next: NextFunction) {
    try {
      const task = await taskService.patchTask(req.params.id, req.body as PatchTaskDto);
      res.json({ data: task });
    } catch (error) { next(error); }
  },

  async delete(req: Request, res: Response, next: NextFunction) {
    try {
      await taskService.deleteTask(req.params.id);
      res.status(204).send();
    } catch (error) { next(error); }
  }
};
