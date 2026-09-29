import { defineStore } from 'pinia'

const ADMIN_UNIT_KEY = 'admin_unit'
const DEFAULT_UNIT = '第一分公司'

export const useSessionStore = defineStore('session', {
  state: () => ({
    operator: '值班管理员',
    shiftLabel: '白班 08:00-20:00',
    scope: '特种设备点检运维平台',
    // 当前登录管理员所属单位：决定作业人员证照的维护权限边界
    adminUnit: localStorage.getItem(ADMIN_UNIT_KEY) || DEFAULT_UNIT,
  }),
  getters: {
    canOperate: (state) => state.operator.length > 0,
  },
  actions: {
    setShift(label: string) {
      this.shiftLabel = label
    },
    setAdminUnit(unit: string) {
      this.adminUnit = unit
      localStorage.setItem(ADMIN_UNIT_KEY, unit)
    },
  },
})
