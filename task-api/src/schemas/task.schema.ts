import { z } from 'zod';

export const TaskPriorityEnum = z.enum(['low', 'medium', 'high']);

export const TaskSchema = z.object({
  id: z.string().uuid(),
  title: z.string().min(1).max(255),
  description: z.string().max(2000).nullable(),
  completed: z.boolean(),
  priority: TaskPriorityEnum,
  dueDate: z.string().datetime().nullable(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime(),
});

export const CreateTaskSchema = z.object({
  title: z.string().min(1).max(255),
  description: z.string().max(2000).optional().nullable(),
  completed: z.boolean().optional().default(false),
  priority: TaskPriorityEnum.optional().default('medium'),
  dueDate: z.string().datetime().optional().nullable(),
});

export const UpdateTaskSchema = z.object({
  title: z.string().min(1).max(255),
  description: z.string().max(2000).nullable(),
  completed: z.boolean(),
  priority: TaskPriorityEnum,
  dueDate: z.string().datetime().nullable(),
});

export const PatchTaskSchema = CreateTaskSchema.partial();

export const TaskQuerySchema = z.object({
  completed: z.enum(['true', 'false']).optional(),
  priority: TaskPriorityEnum.optional(),
  sort: z.enum(['createdAt', 'dueDate', 'priority']).optional(),
  order: z.enum(['asc', 'desc']).optional().default('desc'),
});

export type Task = z.infer<typeof TaskSchema>;
export type CreateTaskDto = z.infer<typeof CreateTaskSchema>;
export type UpdateTaskDto = z.infer<typeof UpdateTaskSchema>;
export type PatchTaskDto = z.infer<typeof PatchTaskSchema>;
export type TaskQuery = z.infer<typeof TaskQuerySchema>;
