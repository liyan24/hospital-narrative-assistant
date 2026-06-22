import React, { createContext, useContext, useState, useMemo, useEffect } from 'react'
import { getFeatures } from '../api/index.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(localStorage.getItem('token') || '')
  const [user, setUser] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('user') || '{}')
    } catch {
      return {}
    }
  })
  const [features, setFeatures] = useState({})

  const roles = user?.roles || []
  const permissions = user?.permissions || []

  const isAdmin = useMemo(() => {
    return roles.some((r) => r.role_code === 'admin') || user?.role === 'admin'
  }, [roles, user])

  const roleCode = useMemo(() => {
    const code = roles[0]?.role_code
    if (code) return code
    return user?.role || 'attending_doctor'
  }, [roles, user])

  const hasPermission = (code) => permissions.includes(code)

  const setAuth = (authData) => {
    const newToken = authData.token || ''
    const newUser = authData.user || { name: '医生', role: 'attending_doctor' }
    setToken(newToken)
    setUser(newUser)
    localStorage.setItem('token', newToken)
    localStorage.setItem('user', JSON.stringify(newUser))
  }

  const logout = () => {
    setToken('')
    setUser({})
    setFeatures({})
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  const loadFeatures = async () => {
    if (!token) return
    try {
      const data = await getFeatures()
      setFeatures(data || {})
    } catch {
      setFeatures({})
    }
  }

  useEffect(() => {
    loadFeatures()
  }, [token])

  const value = useMemo(
    () => ({
      token,
      user,
      roles,
      roleCode,
      permissions,
      isAdmin,
      features,
      hasPermission,
      setAuth,
      logout,
      refreshFeatures: loadFeatures,
    }),
    [token, user, roles, roleCode, permissions, isAdmin, features]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuthStore() {
  return useContext(AuthContext)
}
