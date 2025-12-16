// Frontend/src/pages/TemplateEditor.jsx

import React, { useState, useEffect, useCallback, useContext } from 'react';

// --- Component Imports ---
import StyledButton from '../components/Template/StyledButton.jsx'; 
// FIX: Changed import name from 'InputComponent' back to a standard convention 
// (or whatever the component is actually exported as from StyledInput.jsx).
// Assuming it is exported as StyledInput.
import StyledInput from '../components/Template/StyledInput.jsx'; 

// FIX: Import the ThemeContext (and optionally the custom hook) from the dedicated context file.
// I will use the common practice of importing the custom hook: useTheme
import { useTheme } from '../context/ThemeContext';

import { 
    FaSave, 
    FaSyncAlt, 
    FaCogs, 
    FaDownload, 
    FaCheckCircle, 
    FaTimesCircle, 
    FaUserCircle 
} from 'react-icons/fa';


// Initial state for the template fields
const initialTemplateState = {
    dept_name: '',
    seating_plan_title: '',
    exam_details: '',
    branch_text: '',
    room_number: '',
    coordinator_name: '',
    coordinator_title: '',
    banner_image_path: '',
};

function TemplateEditor({ showToast }) { // Assuming showToast might be passed if using the old App.jsx logic
    
    // 1. Consume the theme context using the custom hook
    // FIX: Using the imported useTheme hook instead of useContext(ThemeContext)
    const { theme } = useTheme();

    const [template, setTemplate] = useState(initialTemplateState);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [generating, setGenerating] = useState(false);
    const [message, setMessage] = useState('');
    const [error, setError] = useState('');

    const clearMessages = useCallback(() => {
        const timer = setTimeout(() => {
            setMessage('');
            setError('');
        }, 5000);
        return () => clearTimeout(timer);
    }, []);

    // -----------------------------------------------------------
    // BACKEND LOGIC (NO CHANGES)
    // -----------------------------------------------------------
    const loadTemplate = useCallback(async () => {
        setError('');
        setMessage('');
        try {
            setLoading(true);
            const response = await fetch('/api/template-config');
            const data = await response.json();
            
            if (data.success) {
                setTemplate(data.template || initialTemplateState);
                setMessage('Template loaded successfully.');
            } else {
                setError(data.error || 'Failed to load template configuration.');
            }
        } catch (err) {
            setError('Failed to connect to server: ' + err.message);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadTemplate();
    }, [loadTemplate]);
    
    useEffect(() => {
        return clearMessages();
    }, [message, error, clearMessages]);

    const handleInputChange = (field, value) => {
        setTemplate(prev => ({ ...prev, [field]: value }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setSaving(true);
        setError('');
        setMessage('');

        const formData = new FormData();
        
        // Add all text fields
        Object.keys(template).forEach(key => {
            if (key !== 'banner_image_path' && template[key]) {
                formData.append(key, template[key]);
            }
        });

        // Add banner image file
        const fileInput = document.getElementById('bannerImage');
        if (fileInput?.files[0]) {
            formData.append('bannerImage', fileInput.files[0]);
        }

        try {
            const response = await fetch('/api/template-config', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (data.success) {
                setMessage(data.message || 'Template saved successfully!');
                setTemplate(data.template); 
                if (fileInput) fileInput.value = '';
            } else {
                setError(data.error || 'Failed to save template.');
            }
        } catch (err) {
            setError('Failed to save template: ' + err.message);
        } finally {
            setSaving(false);
        }
    };

    const generateTestPDF = async () => {
        setGenerating(true);
        setError('');
        setMessage('');

        try {
            const response = await fetch('/api/test-pdf', { method: 'GET' });

            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = url;
                link.download = `test_seating_plan_${new Date().getTime()}.pdf`;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                window.URL.revokeObjectURL(url);
                
                setMessage('Test PDF generated and downloaded successfully!');
            } else {
                const errorData = await response.json().catch(() => ({ error: 'Unknown server error.' }));
                setError(errorData.error || `Failed to generate test PDF (Status: ${response.status})`);
            }
        } catch (err) {
            setError('Failed to generate test PDF: ' + err.message);
        } finally {
            setGenerating(false);
        }
    };
    // -----------------------------------------------------------
    // END OF BACKEND LOGIC
    // -----------------------------------------------------------


    // --- RENDER LOGIC (Theme-aware Tailwind Classes for Layout) ---
    
    // ⚡ MAX DARKNESS: Main card container bg set to dark:bg-gray-950 (or will use 900 if 950 is not configured)
    const cardBgClass = "bg-white dark:bg-gray-950 shadow-2xl"; 
    
    // ⚡ MAX DARKNESS: Inner section bg set to dark:bg-gray-900 (was gray-800) and border to dark:border-gray-800
    const sectionBgClass = "bg-gray-100 dark:bg-gray-900 border-gray-200 dark:border-gray-800";
    
    const textClass = "text-gray-900 dark:text-white";
    const labelTextClass = "text-gray-700 dark:text-gray-300";
    const headerBorderClass = "border-indigo-400 dark:border-indigo-500";
    
    // ⚡ DARKER: Read-only input bg to dark:bg-gray-800 (was gray-700) and border to dark:border-gray-700
    const readOnlyInputClass = "w-full p-3 rounded-lg bg-gray-200 text-gray-600 dark:bg-gray-800 dark:text-gray-400 border border-gray-300 dark:border-gray-700";
    
    // ⚡ MAX DARKNESS: Preview outer container bg set to dark:bg-gray-900 (was gray-800) and border to dark:border-gray-700
    const previewContainerClass = "bg-gray-50 dark:bg-gray-900 border-gray-300 dark:border-gray-700";
    
    // ⚡ MAX DARKNESS: Preview inner content bg set to dark:bg-gray-950 (or 900 if 950 fails)
    const previewContentClass = "bg-white dark:bg-gray-950 border-indigo-300 dark:border-indigo-500 text-gray-700 dark:text-gray-300";


    if (loading) {
        return (
            <div className={`max-w-6xl mx-auto mt-10 ${cardBgClass} rounded-xl shadow-lg p-6`}>
                <div className="header text-center py-8 bg-indigo-900 text-white rounded-t-lg">
                    <h1>PDF Template Editor</h1>
                </div>
                <div className={`loading text-center py-10 ${labelTextClass}`}>
                    <FaSyncAlt className="animate-spin inline-block mr-2" />
                    <h3>Loading template configuration...</h3>
                </div>
            </div>
        );
    }

    return (
        <div className={`w-full max-w-6xl mx-auto p-6 ${textClass}`}>
            <div className={`rounded-xl overflow-hidden ${cardBgClass}`}>
                
                {/* Header Section */}
                <div className="bg-indigo-900 text-white p-6 text-center">
                    <h1 className="text-3xl font-extrabold flex items-center justify-center">
                        <FaCogs className="mr-3 text-yellow-400 text-4xl" /> PDF Template Editor
                    </h1>
                    <p className="text-indigo-200 mt-1">Customize your PDF templates for seating plans</p>
                    <p className="text-sm text-yellow-300 mt-3 p-1 bg-indigo-800 inline-block rounded-full px-3">
                        <FaUserCircle className="inline mr-1" /> Currently editing template for: **test_user**
                    </p>
                </div>

                <div className="p-8">
                    {/* Message and Error Alerts */}
                    {message && (
                        <div className="flex items-center alert bg-green-50 border border-green-300 text-green-700 dark:bg-green-900 dark:border-green-700 dark:text-green-300 p-4 rounded-lg mb-6 shadow-sm">
                            <FaCheckCircle className="mr-3 text-xl" /> <strong>Success:</strong> {message}
                        </div>
                    )}

                    {error && (
                        <div className="flex items-center alert bg-red-50 border border-red-300 text-red-700 dark:bg-red-900 dark:border-red-700 dark:text-red-300 p-4 rounded-lg mb-6 shadow-sm">
                            <FaTimesCircle className="mr-3 text-xl" /> <strong>Error:</strong> {error}
                        </div>
                    )}

                    <form onSubmit={handleSubmit}>
                        
                        {/* Header Information */}
                        <div className={`${sectionBgClass} rounded p-6 mb-8 shadow-inner border`}>
                            {/* Icons intentionally removed by user */}
                            <h3 className={`text-2xl font-bold ${textClass} mb-4 pb-2 border-b-2 ${headerBorderClass} font-bogle`}> Header Information</h3>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <div className="space-y-2">
                                    <label className={`block text-sm font-medium ${labelTextClass}`}>Department Name:</label>
                                    <StyledInput // FIX: Using the corrected import name
                                        type="text"
                                        value={template.dept_name || ''}
                                        onChange={(e) => handleInputChange('dept_name', e.target.value)}
                                        placeholder="e.g., Department of Computer Science & Engineering"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <label className={`block text-sm font-medium ${labelTextClass}`}>Seating Plan Title:</label>
                                    <StyledInput // FIX: Using the corrected import name
                                        type="text"
                                        value={template.seating_plan_title || ''}
                                        onChange={(e) => handleInputChange('seating_plan_title', e.target.value)}
                                        placeholder="e.g., Seating Plan"
                                    />
                                </div>
                            </div>
                            
                            <div className="mt-4 space-y-2">
                                <label className={`block text-sm font-medium ${labelTextClass}`}>Exam Details:</label>
                                {/* Assuming StyledInput can handle textarea via props or separate component */}
                                <StyledInput 
                                    type="textarea"
                                    rows="2"
                                    value={template.exam_details || ''}
                                    onChange={(e) => handleInputChange('exam_details', e.target.value)}
                                    placeholder="e.g., Minor-II Examination (2025 Admitted), November 2025"
                                />
                            </div>
                        </div>

                        {/* Branch and Room Information */}
                        <div className={`${sectionBgClass} rounded p-6 mb-8 shadow-inner border`}>
                            {/* Icons intentionally removed by user */}
                            <h3 className={`text-2xl font-bold ${textClass} mb-4 pb-2 border-b-2 ${headerBorderClass} font-bogle`}> Branch and Room Information</h3>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <div className="space-y-2">
                                    <label className={`block text-sm font-medium ${labelTextClass}`}>Branch Text:</label>
                                    <StyledInput // FIX: Using the corrected import name
                                        type="text"
                                        value={template.branch_text || ''}
                                        onChange={(e) => handleInputChange('branch_text', e.target.value)}
                                        placeholder="e.g., Branch: B.Tech(CSE & CSD Ist year)"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <label className={`block text-sm font-medium ${labelTextClass}`}>Room Number:</label>
                                    <StyledInput // FIX: Using the corrected import name
                                        type="text"
                                        value={template.room_number || ''}
                                        onChange={(e) => handleInputChange('room_number', e.target.value)}
                                        placeholder="e.g., Room no. 103A"
                                    />
                                </div>
                            </div>
                        </div>

                        {/* Coordinator Information */}
                        <div className={`${sectionBgClass} rounded p-6 mb-8 shadow-inner border`}>
                            {/* Icons intentionally removed by user */}
                            <h3 className={`text-2xl font-bold ${textClass} mb-4 pb-2 border-b-2 ${headerBorderClass} font-bogle`}> Coordinator/Signature Information</h3>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <div className="space-y-2">
                                    <label className={`block text-sm font-medium ${labelTextClass}`}>Coordinator Name:</label>
                                    <StyledInput // FIX: Using the corrected import name
                                        type="text"
                                        value={template.coordinator_name || ''}
                                        onChange={(e) => handleInputChange('coordinator_name', e.target.value)}
                                        placeholder="e.g., Dr. Dheeraj K. Dixit"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <label className={`block text-sm font-medium ${labelTextClass}`}>Coordinator Title:</label>
                                    <StyledInput // FIX: Using the corrected import name
                                        type="text"
                                        value={template.coordinator_title || ''}
                                        onChange={(e) => handleInputChange('coordinator_title', e.target.value)}
                                        placeholder="e.g., Dept. Exam Coordinator"
                                    />
                                </div>
                            </div>
                        </div>

                        {/* Banner Image */}
                        <div className={`${sectionBgClass} rounded p-6 mb-8 shadow-inner border`}>
                            {/* Icons intentionally removed by user */}
                            <h3 className={`text-2xl font-bold ${textClass} mb-4 pb-2 border-b-2 ${headerBorderClass} font-bogle`}> Banner/Logo Image</h3>
                            <div className="space-y-4">
                                <div className="space-y-2">
                                    <label className={`block text-sm font-medium ${labelTextClass}`}>Current Banner Path:</label>
                                    <input
                                        type="text"
                                        value={template.banner_image_path || 'No image set'}
                                        readOnly
                                        className={readOnlyInputClass}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <label htmlFor="bannerImage" className={`block text-sm font-medium ${labelTextClass}`}>Upload New Banner (optional):</label>
                                    <input
                                        type="file"
                                        id="bannerImage"
                                        accept="image/*"
                                        className="w-full text-gray-700 dark:text-gray-300 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100 dark:file:bg-indigo-800 dark:file:text-indigo-300 dark:hover:file:bg-indigo-700 cursor-pointer"
                                    />
                                    <small className="text-gray-500 dark:text-gray-400 mt-1 block">
                                        Supported formats: PNG, JPG, JPEG. The file will be sent via FormData.
                                    </small>
                                </div>
                            </div>
                        </div>

                        {/* Action Buttons (StyledButton usage is correct) */}
                        <div className="text-center pt-6 border-t border-gray-300 dark:border-gray-600 flex flex-wrap justify-center space-x-4">
                            
                            {/* Save Button */}
                            <StyledButton 
                                type="submit" 
                                disabled={saving}
                                variant="save"
                            >
                                {saving ? <><FaSave className="inline mr-2 animate-pulse" /> Saving...</> : <><FaSave className="inline mr-2" /> Save Template</>}
                            </StyledButton>

                            {/* Generate PDF Button */}
                            <StyledButton 
                                onClick={generateTestPDF}
                                disabled={generating}
                                variant="download"
                            >
                                {generating ? <><FaSyncAlt className="inline mr-2 animate-spin" /> Generating...</> : <><FaDownload className="inline mr-2" /> Generate Test PDF</>}
                            </StyledButton>

                            {/* Reload Button */}
                            <StyledButton 
                                onClick={loadTemplate}
                                variant="reload"
                            >
                                <FaSyncAlt className="inline mr-2" /> Reload Template
                            </StyledButton>
                        </div>
                    </form>

                    {/* Preview Section */}
                    <div className={`mt-10 rounded-xl p-6 shadow-inner border ${previewContainerClass}`}>
                        <h3 className={`text-2xl font-bold ${textClass} mb-4 pb-2 border-b-2 border-gray-400 dark:border-gray-500`}> Current Configuration Preview</h3>
                        <div className={`p-4 rounded border-2 border-dashed text-sm overflow-auto space-y-1 ${previewContentClass}`}>
                            <p><strong>Department:</strong> {template.dept_name || 'Not set'}</p>
                            <p><strong>Title:</strong> {template.seating_plan_title || 'Not set'}</p>
                            <p><strong>Exam Details:</strong> {template.exam_details || 'Not set'}</p>
                            <p><strong>Branch Text:</strong> {template.branch_text || 'Not set'}</p>
                            <p><strong>Room:</strong> {template.room_number || 'Not set'}</p>
                            <p><strong>Coordinator:</strong> {template.coordinator_name || 'Not set'} - {template.coordinator_title || 'Not set'}</p>
                            <p><strong>Banner Path:</strong> {template.banner_image_path || 'Not set'}</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default TemplateEditor;