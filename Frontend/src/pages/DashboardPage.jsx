import React from 'react';
import { Users, Layout, MapPin, Download, Upload, CheckCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const DashboardPage = ({ setCurrentPage }) => {
  const { user } = useAuth();

  const stats = [
    { label: 'Total Students', value: '1,245', icon: Users, color: 'bg-blue-500' },
    { label: 'Classrooms', value: '24', icon: Layout, color: 'bg-green-500' },
    { label: 'Allocations', value: '48', icon: MapPin, color: 'bg-purple-500' },
    { label: 'Reports', value: '156', icon: Download, color: 'bg-orange-500' }
  ];

  const quickActions = [
    { label: 'Upload Students', page: 'upload', icon: Upload, color: 'bg-blue-500' },
    { label: 'Configure Layout', page: 'layout', icon: Layout, color: 'bg-green-500' },
    { label: 'View Allocation', page: 'allocation', icon: MapPin, color: 'bg-purple-500' },
    { label: 'Download Report', page: 'allocation', icon: Download, color: 'bg-orange-500' }
  ];

  return (
    <div className="min-h-screen bg-black-50 py-8 px-4">
      <div className="max-w-7xl mx-auto">
        {/* Welcome Section */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">
            Welcome back, {user?.name}!
          </h1>
          <p className="text-gray-600 mt-2">
            Here's what's happening with your seat allocations today.
          </p>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          {stats.map((stat, index) => (
            <div
              key={index}
              className="bg-white p-6 rounded-xl shadow-md hover:shadow-lg transition"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-gray-500 text-sm">{stat.label}</p>
                  <p className="text-3xl font-bold text-gray-900 mt-2">{stat.value}</p>
                </div>
                <div className={`${stat.color} p-3 rounded-lg`}>
                  <stat.icon className="text-white" size={24} />
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Quick Actions */}
        <div className="bg-white rounded-xl shadow-md p-6 mb-8">
          <h2 className="text-xl font-bold text-gray-900 mb-6">Quick Actions</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {quickActions.map((action, index) => (
              <button
                key={index}
                onClick={() => setCurrentPage(action.page)}
                className="flex flex-col items-center gap-3 p-6 border-2 border-gray-200 rounded-lg hover:border-blue-500 hover:shadow-md transition"
              >
                <div className={`${action.color} p-3 rounded-lg`}>
                  <action.icon className="text-white" size={24} />
                </div>
                <span className="font-medium text-gray-700">{action.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Recent Activity */}
        <div className="bg-white rounded-xl shadow-md p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-6">Recent Activity</h2>
          <div className="space-y-4">
            {[
              { text: 'Seat allocation completed for Classroom A', time: '2 hours ago', status: 'success' },
              { text: 'Student data uploaded successfully', time: '5 hours ago', status: 'success' },
              { text: 'PDF report generated', time: '1 day ago', status: 'success' }
            ].map((activity, index) => (
              <div
                key={index}
                className="flex items-center justify-between p-4 bg-gray-50 rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <CheckCircle className="text-green-500" size={20} />
                  <div>
                    <p className="font-medium text-gray-900">{activity.text}</p>
                    <p className="text-sm text-gray-500">{activity.time}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;