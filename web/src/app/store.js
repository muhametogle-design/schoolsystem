import { configureStore } from '@reduxjs/toolkit';
import authReducer from '../features/auth/authSlice';
import studentReducer from '../features/students/studentSlice';
import attendanceReducer from '../features/attendance/attendanceSlice';
import schoolReducer from '../features/schools/schoolSlice';

export const store = configureStore({
  reducer: {
    auth: authReducer,
    students: studentReducer,
    attendance: attendanceReducer,
    schools: schoolReducer,
  },
});
