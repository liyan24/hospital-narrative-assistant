import { Navigate } from 'react-router-dom'
import { useAuthStore } from '../stores/auth.jsx'

import PortalLayout from '../layouts/PortalLayout.jsx'
import AdminLayout from '../layouts/AdminLayout.jsx'

import LoginView from '../views/login/LoginView.jsx'
import DashboardView from '../views/portal/DashboardView.jsx'
import PatientSearchView from '../views/portal/PatientSearchView.jsx'
import PatientDetail from '../views/portal/PatientDetailView.jsx'
import WardRound from '../views/portal/WardRoundView.jsx'
import Briefing from '../views/portal/BriefingView.jsx'
import QualityView from '../views/portal/QualityView.jsx'
import SimilarPatientView from '../views/portal/SimilarPatientView.jsx'
import ResearchView from '../views/portal/ResearchView.jsx'

import AdminDashboard from '../views/admin/DashboardView.jsx'
import UserManagement from '../views/admin/UserManagementView.jsx'
import RolePermission from '../views/admin/RolePermissionView.jsx'
import FeatureSwitches from '../views/admin/FeatureSwitchesView.jsx'
import SystemConfig from '../views/admin/SystemConfigView.jsx'
import CacheManagement from '../views/admin/CacheManagementView.jsx'

function RequireAuth({ children }) {
  const { token } = useAuthStore()
  return token ? children : <Navigate to="/login" replace />
}

function RequireAdmin({ children }) {
  const { token, isAdmin } = useAuthStore()
  if (!token) return <Navigate to="/login" replace />
  if (!isAdmin) return <Navigate to="/portal" replace />
  return children
}

const routes = [
  { path: '/login', element: <LoginView /> },
  {
    path: '/portal',
    element: (
      <RequireAuth>
        <PortalLayout />
      </RequireAuth>
    ),
    children: [
      { path: '', element: <DashboardView /> },
      { path: 'patient-search', element: <PatientSearchView /> },
      { path: 'patient/:patientId', element: <PatientDetail /> },
      { path: 'ward-round', element: <WardRound /> },
      { path: 'briefing', element: <Briefing /> },
      { path: 'quality', element: <QualityView /> },
      { path: 'similar-patient', element: <SimilarPatientView /> },
      { path: 'research', element: <ResearchView /> },
    ],
  },
  {
    path: '/admin',
    element: (
      <RequireAdmin>
        <AdminLayout />
      </RequireAdmin>
    ),
    children: [
      { path: '', element: <AdminDashboard /> },
      { path: 'users', element: <UserManagement /> },
      { path: 'roles', element: <RolePermission /> },
      { path: 'features', element: <FeatureSwitches /> },
      { path: 'config', element: <SystemConfig /> },
      { path: 'cache', element: <CacheManagement /> },
    ],
  },
  { path: '/', element: <Navigate to="/portal" replace /> },
]

export default routes
