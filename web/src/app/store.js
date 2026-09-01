import { configureStore } from '@reduxjs/toolkit';
import authReducer from '../features/auth/authSlice';
import studentReducer from '../features/students/studentSlice';
import attendanceReducer from '../features/attendance/attendanceSlice';
import schoolReducer from '../features/schools/schoolSlice';
import uiReducer from '../features/ui/uiSlice';
import absenceReducer from '../features/absences/absenceSlice';
import syllabusReducer from '../features/syllabus/syllabusSlice';
import biometricsReducer from '../features/biometrics/biometricsSlice';
import backupsReducer from '../features/backups/backupsSlice';
import teacherPortalReducer from '../features/teacherPortal/teacherPortalSlice';
import designReducer from '../features/design/designSlice';
import mediaReducer from '../features/media/mediaSlice';

export const store = configureStore({
  reducer: {
    auth: authReducer,
    students: studentReducer,
    attendance: attendanceReducer,
    schools: schoolReducer,
    ui: uiReducer,
    absences: absenceReducer,
    syllabus: syllabusReducer,
    biometrics: biometricsReducer,
    backups: backupsReducer,
    teacherPortal: teacherPortalReducer,
    design: designReducer,
    media: mediaReducer,
  },
});
