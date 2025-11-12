import React, { useState, useEffect } from "react";
import Navbar from "./Navbar";
import { useNavigate } from "react-router-dom"; // Import useNavigate

const UserForm = () => {
  const [formData, setFormData] = useState({
    email: "", // Retained for backend consistency if fetched, but not editable
    first_name: "",
    last_name: "",
    age: "",
    gender: "",
    weight_kg: "",
    height_cm: "",
    contact_number: "",
    address: "",
    allergies: [""],
    surgeries: [{ surgery: "", date: "" }],
    family_history: [""],
    prescriptions: [{ drug: "", dosage: "", frequency: "" ,reason: ""}],
  });
  
  const [saveStatus, setSaveStatus] = useState(null); // 'success', 'error', or null
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();


 useEffect(() => {
    const userId = localStorage.getItem("user_id"); 
    
    if (!userId) {
        // Redirect to signin if no user_id is found
        navigate("/signin");
        return; 
  	}
    
    async function fetchPersonalInfo() {
        setLoading(true);
        try {
          const response = await fetch("http://localhost:8000/api/personal-info", {
            method: "GET",
            headers: {
                "X-User-ID": userId, 
            }
          });

          if (response.ok) {
            const data = await response.json();

            setFormData({
              email: data.email || "",
              first_name: data.first_name || "",
              last_name: data.last_name || "",
              age: data.age || "",
              gender: data.gender || "",
              weight_kg: data.weight_kg || "",
              height_cm: data.height_cm || "",
              contact_number: data.contact_number || "",
              address: data.address || "",
              allergies: Array.isArray(data.allergies) && data.allergies.length > 0 ? data.allergies : [""],
              family_history: Array.isArray(data.family_history) && data.family_history.length > 0 ? data.family_history : [""],
              surgeries: Array.isArray(data.surgeries) && data.surgeries.length > 0
                ? data.surgeries.map((s) => ({
                    surgery: s?.surgery || "",
                    // Date is split to ensure only 'YYYY-MM-DD' is used for input type="date"
                    date: s?.date ? s.date.split("T")[0] : "", 
                  }))
                : [{ surgery: "", date: "" }],
              prescriptions: Array.isArray(data.prescriptions) && data.prescriptions.length > 0
                ? data.prescriptions.map((p) => ({
                    drug: p?.drug || "",
                    dosage: p?.dosage || "",
                    frequency: p?.frequency || "",
                    reason: p?.reason || "",
                  }))
                : [{ drug: "", dosage: "", frequency: "", reason: "" }],
            });
          } else {
            console.warn("No personal info found or fetch failed. Status:", response.status);
          }
        } catch (error) {
          console.error("Failed to fetch personal info:", error);
        } finally {
            setLoading(false);
        }
    }

    fetchPersonalInfo();
    
}, [navigate]); // Dependency array includes navigate


  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

 const handleListChange = (e, index, field) => {
  const updatedList = [...(formData[field] || [])];
  updatedList[index] = e.target.value;
  setFormData((prev) => ({ ...prev, [field]: updatedList }));
};
 
  const handleSurgeryChange = (e, index, field) => {
  const list = [...(formData.surgeries || [])];
  if (!list[index]) list[index] = { surgery: "", date: "" };
  list[index][field] = e.target.value;
  setFormData((prev) => ({ ...prev, surgeries: list }));
};


  const handlePrescriptionChange = (e, index) => {
  const { name, value } = e.target;
  const list = [...(formData.prescriptions || [])];
  if (!list[index]) list[index] = { drug: "", dosage: "", frequency: "", reason: "" };
  list[index][name] = value;
  setFormData((prev) => ({ ...prev, prescriptions: list }));
};
    

  const addListItem = (field) => {
  const updatedList = [...(formData[field] || []), ""];
  setFormData((prev) => ({ ...prev, [field]: updatedList }));
};


  const addPrescription = () => {
    setFormData((prev) => ({
      ...prev,
      prescriptions: [...prev.prescriptions, { drug: "", dosage: "", frequency: "", reason: "" }],
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaveStatus(null); // Clear previous status
    const userId = localStorage.getItem("user_id");

    if (!userId) {
        console.error("Authentication error: User not signed in. Redirecting.");
        navigate("/signin");
        return;
    }


    const payload = {
      ...formData,
      age: formData.age ? parseInt(formData.age) : undefined,
      weight_kg: formData.weight_kg ? parseFloat(formData.weight_kg) : undefined,
      height_cm: formData.height_cm ? parseFloat(formData.height_cm) : undefined,
      allergies: formData.allergies.filter((a) => a.trim() !== ""),
      family_history: formData.family_history.filter((f) => f.trim() !== ""),
      surgeries: formData.surgeries
        .filter(s => s.surgery && s.date)
        .map(s => ({
          surgery: s.surgery,
          date: s.date // 'YYYY-MM-DD'
        })), 
      prescriptions: formData.prescriptions.filter(
        (p) => p.drug && p.dosage && p.frequency && p.reason
      ),
    };

    // Remove email and password to prevent accidental update/exposure
    delete payload.email;
    delete payload.password;


    try {
      const response = await fetch("http://localhost:8000/api/personal-info", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-User-ID": userId, 
        },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        setSaveStatus('success');
      } else {
        const err = await response.json();
        console.error("Server error detail:", err.detail);
        setSaveStatus('error');
      }
    } catch (error) {
      console.error("Error submitting form:", error);
      setSaveStatus('error');
    }
  };


if (loading) {
    return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
            <p className="text-xl font-medium text-indigo-600 dark:text-indigo-400">Loading user data...</p>
        </div>
    );
}


  return (
    <div className="flex justify-center items-start min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
       <Navbar />
      <div className="w-full max-w-4xl bg-white dark:bg-gray-800 shadow-lg rounded-xl p-8 mt-16">
        <h2 className="text-3xl font-bold text-gray-800 dark:text-white mb-8 text-center border-b pb-4 border-gray-200 dark:border-gray-700">
          Your Personal Health Profile
        </h2>
        
        {saveStatus === 'success' && (
            <div className="bg-green-100 text-green-700 p-3 rounded-lg mb-4 text-center font-medium">
                Data saved successfully! You can now use the ChatBot.
            </div>
        )}
        {saveStatus === 'error' && (
            <div className="bg-red-100 text-red-700 p-3 rounded-lg mb-4 text-center font-medium">
                Failed to save data. Please check the console for server details.
            </div>
        )}


        <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Personal Details Section */}
          {[
            ["First Name", "first_name", "text"],
            ["Last Name", "last_name", "text"],
            ["Age", "age", "number"],
            ["Gender", "gender", "select"],
            ["Weight (kg)", "weight_kg", "number"],
            ["Height (cm)", "height_cm", "number"],
            ["Contact Number", "contact_number", "tel"],
            ["Address", "address", "text"],
          ].map(([label, name, type]) => (
            <div key={name}>
              <label htmlFor={name} className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                {label}
              </label>
              { name === "gender" ? (
  <select
    id={name}
    name={name}
    value={formData[name]}
    onChange={handleChange}
    className="mt-1 block w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white p-3 focus:ring-indigo-500 focus:border-indigo-500"
  >
    <option value="">Select Gender</option>
    <option value="Male">Male</option>
    <option value="Female">Female</option>
    <option value="Prefer not to say">Prefer not to say</option>
  </select>
) : (
  <input
    id={name}
    name={name}
    type={type}
    value={formData[name]}
    onChange={handleChange}
    className="mt-1 block w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white p-3 focus:ring-indigo-500 focus:border-indigo-500"
    placeholder={`Enter ${label}`}
     // Disable email field if it exists in state
    disabled={name === 'email'}
  />
)}

            </div>
          ))}
          
          {/* Allergies and Family History Section */}
          {["allergies", "family_history"].map((field) => (
  <div key={field} className="col-span-full border-t pt-4 border-gray-100 dark:border-gray-700">
    <label className="block text-lg font-semibold text-gray-700 dark:text-gray-300 capitalize mb-2">
      {field.replace("_", " ")}
    </label>
    {formData[field].map((item, index) => (
      <input
        key={index}
        value={item}
        onChange={(e) => handleListChange(e, index, field)}
        className="mt-1 mb-2 block w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white p-3"
        placeholder={`e.g., Penicillin (if allergies) or Diabetes (if family history)`}
      />
    ))}
    <button
      type="button"
      onClick={() => addListItem(field)}
      className="text-indigo-500 hover:text-indigo-400 text-sm mb-4 font-medium"
    >
      + Add another {field.replace("_", " ").slice(0, -1)}
    </button>
  </div>
))}

          {/* Surgeries Section */}
          <div className="col-span-full border-t pt-4 border-gray-100 dark:border-gray-700">
  <label className="block text-lg font-semibold text-gray-700 dark:text-gray-300 capitalize mb-2">
    Surgeries History
  </label>
  {formData.surgeries.map((item, index) => (
    <div key={index} className="flex flex-col sm:flex-row gap-3 mb-3 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg border border-gray-200 dark:border-gray-600">
      <input
        type="text"
        value={item.surgery}
        onChange={(e) => handleSurgeryChange(e, index, "surgery")}
        className="w-full sm:w-2/3 rounded-lg border border-gray-300 dark:border-gray-600 p-2 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
        placeholder="Type of Surgery (e.g., Appendectomy)"
      />
      <input
        type="date"
        value={item.date}
        onChange={(e) => handleSurgeryChange(e, index, "date")}
        className="w-full sm:w-1/3 rounded-lg border border-gray-300 dark:border-gray-600 p-2 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
        placeholder="Date"
      />
    </div>
  ))}
  <button
    type="button"
    onClick={() => setFormData((prev) => ({
      ...prev,
      surgeries: [...prev.surgeries, { surgery: "", date: "" }]
    }))}
    className="text-indigo-500 hover:text-indigo-400 text-sm mb-4 font-medium"
  >
    + Add another surgery
  </button>
</div>


          {/* Prescriptions Section */}
          <div className="col-span-full border-t pt-4 border-gray-100 dark:border-gray-700">
            <label className="block text-lg font-semibold text-gray-700 dark:text-gray-300 mb-2">
              Current Prescriptions (Drug, Dosage, Frequency, Reason)
            </label>
            {formData.prescriptions.map((entry, index) => (
              <div key={index} className="flex flex-col md:flex-row gap-2 mb-3 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg border border-gray-200 dark:border-gray-600">
                <input
                  type="text"
                  name="drug"
                  placeholder="Drug Name (e.g., Lisinopril)"
                  value={entry.drug}
                  onChange={(e) => handlePrescriptionChange(e, index)}
                  className="w-full md:w-1/4 rounded-lg border border-gray-300 dark:border-gray-600 p-2 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                />
                <input
                  type="text"
                  name="dosage"
                  placeholder="Dosage (e.g., 10mg)"
                  value={entry.dosage}
                  onChange={(e) => handlePrescriptionChange(e, index)}
                  className="w-full md:w-1/4 rounded-lg border border-gray-300 dark:border-gray-600 p-2 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                />
                <input
                  type="text"
                  name="frequency"
                  placeholder="Frequency (e.g., Once daily)"
                  value={entry.frequency}
                  onChange={(e) => handlePrescriptionChange(e, index)}
                  className="w-full md:w-1/4 rounded-lg border border-gray-300 dark:border-gray-600 p-2 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                />
                <input
                  type="text"
                  name="reason"
                  placeholder="Reason (e.g., High Blood Pressure)"
                  value={entry.reason}
                  onChange={(e) => handlePrescriptionChange(e, index)}
                  className="w-full md:w-1/4 rounded-lg border border-gray-300 dark:border-gray-600 p-2 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                />
              </div>
            ))}
            <button
              type="button"
              onClick={addPrescription}
              className="text-indigo-500 hover:text-indigo-400 text-sm mb-4 font-medium"
            >
              + Add prescription
            </button>
          </div>

          <div className="col-span-full flex justify-center mt-6">
            <button
              type="submit"
              className="px-8 py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-lg shadow-lg transition duration-200"
            >
              Save & Continue to Chat
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default UserForm;
