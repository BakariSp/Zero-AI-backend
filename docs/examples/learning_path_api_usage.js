// Example of using the new user-specific endpoint with progress information

/**
 * OLD APPROACH: Two separate API calls
 * 1. Get the learning path content
 * 2. Get the user's progress for the learning path
 */
async function oldApproach(pathId, userId) {
  try {
    // First API call to get learning path content
    const learningPathResponse = await fetch(`/api/learning-paths/${pathId}`);
    const learningPathData = await learningPathResponse.json();
    
    // Second API call to get user's progress (hypothetical endpoint)
    const progressResponse = await fetch(`/api/users/${userId}/progress/learning-paths/${pathId}`);
    const progressData = await progressResponse.json();
    
    // Combine data client-side
    return {
      ...learningPathData,
      userProgress: progressData.progress,
      startDate: progressData.start_date,
      completedAt: progressData.completed_at
    };
  } catch (error) {
    console.error('Error fetching learning path data:', error);
    throw error;
  }
}

/**
 * NEW APPROACH: Single API call with user-specific data
 * Get everything in one request with the new endpoint
 */
async function newApproach(pathId) {
  try {
    // Single API call to get both learning path content and user progress
    const response = await fetch(`/api/users/me/learning-paths/${pathId}`, {
      headers: {
        'Authorization': `Bearer ${getAuthToken()}` // User authentication required
      }
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    // All data combined in one response
    const data = await response.json();
    
    // Data structure provides access to both learning path content and user progress
    return {
      id: data.learning_path_id,
      title: data.learning_path.title,
      description: data.learning_path.description,
      category: data.learning_path.category,
      sections: data.learning_path.sections,
      courses: data.learning_path.courses,
      // User-specific data
      progress: data.progress,
      startDate: data.start_date,
      completedAt: data.completed_at,
      userId: data.user_id
    };
  } catch (error) {
    console.error('Error fetching user learning path data:', error);
    throw error;
  }
}

/**
 * Example usage in a React component
 */
function LearningPathPage({ pathId }) {
  const [learningPath, setLearningPath] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        // Use the new approach for better performance
        const data = await newApproach(pathId);
        setLearningPath(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    
    fetchData();
  }, [pathId]);
  
  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error}</div>;
  if (!learningPath) return <div>No learning path found</div>;
  
  return (
    <div>
      <h1>{learningPath.title}</h1>
      <p>{learningPath.description}</p>
      
      {/* Display user progress */}
      <ProgressBar value={learningPath.progress} />
      
      {/* Display start date */}
      <p>Started: {new Date(learningPath.startDate).toLocaleDateString()}</p>
      
      {/* Display completion status */}
      {learningPath.completedAt && (
        <p>Completed: {new Date(learningPath.completedAt).toLocaleDateString()}</p>
      )}
      
      {/* Display learning path content */}
      <h2>Courses</h2>
      <CoursesList courses={learningPath.courses} />
      
      {/* Other UI components */}
    </div>
  );
} 