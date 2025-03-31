document.addEventListener('DOMContentLoaded', function() {
    // Poll type change handler - show/hide institution field
    const pollTypeSelect = document.getElementById('id_poll_type');
    const institutionField = document.getElementById('institution-field');
    
    pollTypeSelect.addEventListener('change', function() {
        if (this.value === 'institution') {
            institutionField.style.display = 'block';
        } else {
            institutionField.style.display = 'none';
        }
    });
    
    // Initialize institution field visibility
    if (pollTypeSelect.value === 'institution') {
        institutionField.style.display = 'block';
    }
    
    // Question formset management
    const questionFormsetPrefix = 'question_set';
    const questionsContainer = document.getElementById('questions-container');
    const addQuestionBtn = document.getElementById('add-question');
    const totalFormsInput = document.getElementById(`id_${questionFormsetPrefix}-TOTAL_FORMS`);
    let formCount = parseInt(totalFormsInput.value);
    
    // Function to update form indices
    function updateFormIndices() {
        const questionForms = questionsContainer.querySelectorAll('.question-form');
        questionForms.forEach((form, index) => {
            form.querySelector('.question-number').textContent = index + 1;
            
            // Update order field with the new index if it's the default value
            const orderInput = form.querySelector(`input[name$="-order"]`);
            if (orderInput && (orderInput.value === '' || orderInput.value === '0')) {
                orderInput.value = index;
            }
            
            // Update DELETE field if marked for deletion
            const deleteInput = form.querySelector(`input[name$="-DELETE"]`);
            if (deleteInput && form.classList.contains('to-delete')) {
                deleteInput.value = 'on';
            }
        });
    }
    
    // Function to add a new question form
    addQuestionBtn.addEventListener('click', function() {
        // Clone the first form or create a new one
        let newForm;
        const existingForm = questionsContainer.querySelector('.question-form');
        
        if (existingForm) {
            newForm = existingForm.cloneNode(true);
            
            // Clear values from the cloned form
            newForm.querySelectorAll('input[type="text"], textarea').forEach(input => {
                input.value = '';
            });
            
            // Reset checkboxes
            newForm.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
                checkbox.checked = checkbox.defaultChecked;
            });
            
            // Reset hidden ID field
            const idField = newForm.querySelector(`input[name$="-id"]`);
            if (idField) idField.value = '';
            
            // Reset DELETE field
            const deleteField = newForm.querySelector(`input[name$="-DELETE"]`);
            if (deleteField) deleteField.value = '';
            
            // Reset choices container
            const choicesContainer = newForm.querySelector('.choices-container');
            if (choicesContainer) {
                const choicesList = choicesContainer.querySelector('.choices-list');
                const firstChoice = choicesList.querySelector('.choice-item');
                
                // Clear all choices except the first one
                Array.from(choicesList.querySelectorAll('.choice-item')).forEach((choice, index) => {
                    if (index > 0) choice.remove();
                });
                
                // Clear the first choice value
                if (firstChoice) {
                    firstChoice.querySelector('input').value = '';
                }
            }
        } else {
            // Create a completely new form
            newForm = document.createElement('div');
            newForm.className = 'question-form mb-4 p-3 border rounded';
            newForm.innerHTML = `
                <div class="d-flex justify-content-between mb-2">
                    <h5>Question #<span class="question-number">1</span></h5>
                    <button type="button" class="btn btn-sm btn-outline-danger delete-question">
                        <i class="fas fa-trash"></i> Remove
                    </button>
                </div>
                
                <input type="hidden" name="${questionFormsetPrefix}-${formCount}-id" id="id_${questionFormsetPrefix}-${formCount}-id">
                <input type="hidden" name="${questionFormsetPrefix}-${formCount}-DELETE" id="id_${questionFormsetPrefix}-${formCount}-DELETE">
                
                <div class="row mb-3">
                    <div class="col-md-8">
                        <label class="form-label">Question Text</label>
                        <textarea name="${questionFormsetPrefix}-${formCount}-text" class="form-control" rows="3" required></textarea>
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Question Type</label>
                        <select name="${questionFormsetPrefix}-${formCount}-question_type" class="form-select question-type-select">
                            <!-- Question type options will be populated dynamically -->
                        </select>
                    </div>
                </div>
                
                <div class="row mb-3">
                    <div class="col-md-4">
                        <div class="form-check">
                            <input type="checkbox" name="${questionFormsetPrefix}-${formCount}-is_required" class="form-check-input" checked>
                            <label class="form-check-label">Required</label>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <label class="form-label">Order</label>
                        <input type="number" name="${questionFormsetPrefix}-${formCount}-order" class="form-control" value="${formCount}">
                    </div>
                </div>
                
                <div class="row mb-3 numeric-fields" style="display: none;">
                    <div class="col-md-4">
                        <label class="form-label">Min Value</label>
                        <input type="number" name="${questionFormsetPrefix}-${formCount}-min_value" class="form-control">
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Max Value</label>
                        <input type="number" name="${questionFormsetPrefix}-${formCount}-max_value" class="form-control">
                    </div>
                    <div class="col-md-4 step-value-field">
                        <label class="form-label">Step Value</label>
                        <input type="number" name="${questionFormsetPrefix}-${formCount}-step_value" class="form-control" step="0.1">
                    </div>
                </div>
                
                <div class="choices-container" style="display: none;">
                    <h6 class="mt-3">Choices</h6>
                    <div class="choices-list">
                        <div class="choice-item row mb-2">
                            <div class="col-10">
                                <input type="text" class="form-control choice-text" 
                                       name="${questionFormsetPrefix}-${formCount}-choice-0-text" 
                                       placeholder="Enter choice text">
                                <input type="hidden" name="${questionFormsetPrefix}-${formCount}-choice-0-id">
                                <input type="hidden" name="${questionFormsetPrefix}-${formCount}-choice-0-DELETE" value="">
                                <input type="hidden" name="${questionFormsetPrefix}-${formCount}-choice-0-order" value="0">
                            </div>
                            <div class="col-2">
                                <button type="button" class="btn btn-sm btn-outline-danger remove-choice">
                                    <i class="fas fa-times"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                    <button type="button" class="btn btn-sm btn-outline-secondary mt-2 add-choice">
                        <i class="fas fa-plus"></i> Add Choice
                    </button>
                    <input type="hidden" name="${questionFormsetPrefix}-${formCount}-choice-TOTAL_FORMS" value="1" class="choice-total-forms">
                    <input type="hidden" name="${questionFormsetPrefix}-${formCount}-choice-INITIAL_FORMS" value="0" class="choice-initial-forms">
                    <input type="hidden" name="${questionFormsetPrefix}-${formCount}-choice-MIN_NUM_FORMS" value="0" class="choice-min-forms">
                    <input type="hidden" name="${questionFormsetPrefix}-${formCount}-choice-MAX_NUM_FORMS" value="1000" class="choice-max-forms">
                </div>
                
                <div class="mt-3">
                    <a class="btn btn-sm btn-outline-secondary" data-bs-toggle="collapse" 
                       href="#settings-${questionFormsetPrefix}-${formCount}" role="button">
                        Advanced Settings
                    </a>
                    <div class="collapse mt-2" id="settings-${questionFormsetPrefix}-${formCount}">
                        <div class="card card-body bg-light">
                            <label class="form-label">Settings (JSON)</label>
                            <textarea name="${questionFormsetPrefix}-${formCount}-settings" class="form-control json-settings" rows="3"></textarea>
                            <small class="text-muted">Optional. Advanced settings in JSON format.</small>
                        </div>
                    </div>
                </div>
            `;
            
            // If we need to populate question types dynamically
            const questionTypeSelect = newForm.querySelector('.question-type-select');
            const existingSelect = document.querySelector('.question-type-select');
            if (existingSelect) {
                existingSelect.querySelectorAll('option').forEach(option => {
                    const newOption = document.createElement('option');
                    newOption.value = option.value;
                    newOption.text = option.text;
                    newOption.setAttribute('data-requires-choices', option.getAttribute('data-requires-choices'));
                    questionTypeSelect.appendChild(newOption);
                });
            }
        }
        
        // Update form indices in all form fields
        if (existingForm) {
            const formRegex = new RegExp(`${questionFormsetPrefix}-\\d+`, 'g');
            newForm.innerHTML = newForm.innerHTML.replace(formRegex, `${questionFormsetPrefix}-${formCount}`);
        }
        
        // Remove any potential "to-delete" class
        newForm.classList.remove('to-delete');
        
        // Add the new form to the container
        questionsContainer.appendChild(newForm);
        
        // Increment form count
        formCount++;
        totalFormsInput.value = formCount;
        
        // Update question numbers
        updateFormIndices();
        
        // Re-attach event handlers
        attachQuestionEventHandlers();
    });
    
    // Function to handle question form events
    function attachQuestionEventHandlers() {
        // Delete question buttons
        document.querySelectorAll('.delete-question').forEach(button => {
            button.removeEventListener('click', deleteQuestionHandler);
            button.addEventListener('click', deleteQuestionHandler);
        });
        
        // Question type change handlers
        document.querySelectorAll('.question-type-select').forEach(select => {
            select.removeEventListener('change', questionTypeChangeHandler);
            select.addEventListener('change', questionTypeChangeHandler);
            
            // Trigger change to initialize UI
            select.dispatchEvent(new Event('change'));
        });
        
        // Add choice button handlers
        document.querySelectorAll('.add-choice').forEach(button => {
            button.removeEventListener('click', addChoiceHandler);
            button.addEventListener('click', addChoiceHandler);
        });
        
        // Remove choice button handlers
        document.querySelectorAll('.remove-choice').forEach(button => {
            button.removeEventListener('click', removeChoiceHandler);
            button.addEventListener('click', removeChoiceHandler);
        });
    }
    
    // Handler for deleting questions
    function deleteQuestionHandler() {
        const form = this.closest('.question-form');
        const deleteInput = form.querySelector(`input[name$="-DELETE"]`);
        
        if (deleteInput) {
            // Mark for deletion rather than removing from DOM
            form.classList.add('to-delete');
            form.style.display = 'none';
            deleteInput.value = 'on';
        } else {
            // If no DELETE field (new form), just remove it
            form.remove();
            formCount--;
            totalFormsInput.value = formCount;
        }
        
        updateFormIndices();
    }
    
    // Handler for question type changes
    function questionTypeChangeHandler() {
        const form = this.closest('.question-form');
        const numericFields = form.querySelector('.numeric-fields');
        const choicesContainer = form.querySelector('.choices-container');
        const stepValueField = form.querySelector('.step-value-field');
        const option = this.options[this.selectedIndex];
        const requiresChoices = option.getAttribute('data-requires-choices') === 'true';
        
        // Get the selected option text and convert to lowercase
        const selectedType = this.options[this.selectedIndex].text.toLowerCase();
        
        // More specific type checking
        const isRating = selectedType.includes('rating');
        const isSlider = selectedType.includes('slider');
        const isMultipleChoice = selectedType.includes('multiple choice') || selectedType.includes('single choice');
        
        // Show/hide numeric fields
        numericFields.style.display = (isRating || isSlider) ? 'flex' : 'none';
        
        // Show/hide step value field (only for slider)
        stepValueField.style.display = isSlider ? 'block' : 'none';
        
        // Show/hide choices
        choicesContainer.style.display = requiresChoices ? 'block' : 'none';
        
        // Initialize with at least 2 choices if multiple choice type is selected
        if (isMultipleChoice && choicesContainer.querySelectorAll('.choice-item').length < 2) {
            const addChoiceBtn = choicesContainer.querySelector('.add-choice');
            if (addChoiceBtn) {
                addChoiceBtn.click(); // Add a second choice option
            }
        }
    }
    
    // Handler for adding choices
    function addChoiceHandler() {
        const form = this.closest('.question-form');
        const choicesContainer = form.querySelector('.choices-container');
        const choicesList = form.querySelector('.choices-list');
        
        // Get current question index
        const questionIndexMatch = form.querySelector(`input[name$="-id"]`).name.match(/\d+/);
        const questionIndex = questionIndexMatch ? questionIndexMatch[0] : 0;
        
        // Get total choices count
        const totalFormsInput = choicesContainer.querySelector('.choice-total-forms');
        let choiceCount = parseInt(totalFormsInput.value);
        
        // Create new choice item
        const choiceItem = document.createElement('div');
        choiceItem.className = 'choice-item row mb-2';
        choiceItem.innerHTML = `
            <div class="col-10">
                <input type="text" class="form-control choice-text" 
                       name="${questionFormsetPrefix}-${questionIndex}-choice-${choiceCount}-text" 
                       placeholder="Enter choice text">
                <input type="hidden" name="${questionFormsetPrefix}-${questionIndex}-choice-${choiceCount}-id">
                <input type="hidden" name="${questionFormsetPrefix}-${questionIndex}-choice-${choiceCount}-DELETE" value="">
                <input type="hidden" name="${questionFormsetPrefix}-${questionIndex}-choice-${choiceCount}-order" value="${choiceCount}">
            </div>
            <div class="col-2">
                <button type="button" class="btn btn-sm btn-outline-danger remove-choice">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
        
        // Add remove button handler
        choiceItem.querySelector('.remove-choice').addEventListener('click', removeChoiceHandler);
        
        // Add to choices list
        choicesList.appendChild(choiceItem);
        
        // Update choice count
        choiceCount++;
        totalFormsInput.value = choiceCount;
        
        // Focus the new input
        choiceItem.querySelector('input').focus();
    }
    
    // Handler for removing choices
    function removeChoiceHandler() {
        const choiceItem = this.closest('.choice-item');
        const choicesList = choiceItem.closest('.choices-list');
        const choicesContainer = choiceItem.closest('.choices-container');
        
        if (choicesList.querySelectorAll('.choice-item').length > 1) {
            // Check if this is an existing choice with ID
            const idInput = choiceItem.querySelector('input[name$="-id"]');
            if (idInput && idInput.value) {
                // Mark for deletion instead of removing
                const deleteInput = choiceItem.querySelector('input[name$="-DELETE"]');
                if (deleteInput) {
                    deleteInput.value = 'on';
                    choiceItem.style.display = 'none';
                } else {
                    choiceItem.remove();
                }
            } else {
                // Just remove non-existing choices
                choiceItem.remove();
            }
            
            // Update choice indices
            updateChoiceIndices(choicesContainer);
        } else {
            // Clear value instead of removing if it's the last choice
            choiceItem.querySelector('.choice-text').value = '';
        }
    }
    
    // Function to update choice indices
    function updateChoiceIndices(choicesContainer) {
        const choiceItems = choicesContainer.querySelectorAll('.choice-item:not([style*="display: none"])');
        const totalFormsInput = choicesContainer.querySelector('.choice-total-forms');
        
        // Update TOTAL_FORMS to visible choices count
        totalFormsInput.value = choiceItems.length;
        
        // Update order values
        choiceItems.forEach((item, index) => {
            const orderInput = item.querySelector('input[name$="-order"]');
            if (orderInput) {
                orderInput.value = index;
            }
        });
    }
    
    // Form validation before submit
    document.getElementById('poll-form').addEventListener('submit', function(e) {
        let isValid = true;
        let firstErrorElement = null;
        
        // Check if at least one visible question exists
        const visibleQuestions = Array.from(questionsContainer.querySelectorAll('.question-form'))
            .filter(q => !q.classList.contains('to-delete') && q.style.display !== 'none');
            
        if (visibleQuestions.length === 0) {
            alert("Please add at least one question to your poll");
            isValid = false;
            firstErrorElement = addQuestionBtn;
        }
        
        // Validate each visible question
        visibleQuestions.forEach((form, index) => {
            // Required fields validation
            form.querySelectorAll('input[required], textarea[required], select[required]').forEach(field => {
                if (!field.value.trim()) {
                    field.classList.add('is-invalid');
                    isValid = false;
                    
                    if (!firstErrorElement) {
                        firstErrorElement = field;
                    }
                } else {
                    field.classList.remove('is-invalid');
                }
            });
            
            // Question type specific validation
            const questionTypeSelect = form.querySelector('.question-type-select');
            if (questionTypeSelect) {
                const option = questionTypeSelect.options[questionTypeSelect.selectedIndex];
                const requiresChoices = option.getAttribute('data-requires-choices') === 'true';
                
                if (requiresChoices) {
                    const choiceInputs = form.querySelectorAll('.choice-text');
                    const visibleChoiceInputs = Array.from(choiceInputs).filter(input => 
                        !input.closest('.choice-item').classList.contains('to-delete') && 
                        input.closest('.choice-item').style.display !== 'none'
                    );
                    
                    let validChoicesCount = 0;
                    
                    // Count valid choices (non-empty)
                    visibleChoiceInputs.forEach(input => {
                        if (input.value.trim() !== '') {
                            validChoicesCount++;
                        } else {
                            input.classList.add('is-invalid');
                        }
                    });
                    
                    if (validChoicesCount < 2) {
                        const questionNum = index + 1;
                        alert(`Question #${questionNum} requires at least two valid choices`);
                        isValid = false;
                        
                        if (!firstErrorElement) {
                            firstErrorElement = form;
                        }
                    }
                }
                
                // Validate numeric fields for rating/slider types
                const selectedType = questionTypeSelect.options[questionTypeSelect.selectedIndex].text.toLowerCase();
                const isRating = selectedType.includes('rating');
                const isSlider = selectedType.includes('slider');
                
                if (isRating || isSlider) {
                    const minValueInput = form.querySelector('input[name$="-min_value"]');
                    const maxValueInput = form.querySelector('input[name$="-max_value"]');
                    
                    if (!minValueInput.value) {
                        minValueInput.classList.add('is-invalid');
                        isValid = false;
                        if (!firstErrorElement) firstErrorElement = minValueInput;
                    }
                    
                    if (!maxValueInput.value) {
                        maxValueInput.classList.add('is-invalid');
                        isValid = false;
                        if (!firstErrorElement) firstErrorElement = maxValueInput;
                    }
                    
                    if (minValueInput.value && maxValueInput.value) {
                        if (parseFloat(minValueInput.value) >= parseFloat(maxValueInput.value)) {
                            maxValueInput.classList.add('is-invalid');
                            alert(`Question #${index + 1}: Maximum value must be greater than minimum value`);
                            isValid = false;
                            if (!firstErrorElement) firstErrorElement = maxValueInput;
                        }
                    }
                    
                    if (isSlider) {
                        const stepValueInput = form.querySelector('input[name$="-step_value"]');
                        if (!stepValueInput.value) {
                            stepValueInput.classList.add('is-invalid');
                            isValid = false;
                            if (!firstErrorElement) firstErrorElement = stepValueInput;
                        }
                    }
                }
            }
        });
        
        // Validate poll-specific fields
        const titleInput = document.querySelector('#id_title');
        if (titleInput && !titleInput.value.trim()) {
            titleInput.classList.add('is-invalid');
            isValid = false;
            if (!firstErrorElement) firstErrorElement = titleInput;
        }
        
        // Validate start/end date
        const startDateInput = document.querySelector('#id_start_date');
        const endDateInput = document.querySelector('#id_end_date');
        if (startDateInput && endDateInput && startDateInput.value && endDateInput.value) {
            const startDate = new Date(startDateInput.value);
            const endDate = new Date(endDateInput.value);
            
            if (endDate < startDate) {
                endDateInput.classList.add('is-invalid');
                alert("End date must be after start date");
                isValid = false;
                if (!firstErrorElement) firstErrorElement = endDateInput;
            }
        }
        
        // Check if institution field is required
        const pollTypeValue = pollTypeSelect.value;
        const institutionInput = document.querySelector('#id_restricted_to_institution');
        if (pollTypeValue === 'institution' && institutionInput && !institutionInput.value.trim()) {
            institutionInput.classList.add('is-invalid');
            alert("Institution name is required for institution-specific polls");
            isValid = false;
            if (!firstErrorElement) firstErrorElement = institutionInput;
        }
        
        if (!isValid) {
            e.preventDefault();
            
            // Scroll to first error
            if (firstErrorElement) {
                firstErrorElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }
    });
    
    // Add validation styling to form fields
    document.querySelectorAll('input, textarea, select').forEach(field => {
        field.addEventListener('blur', function() {
            if (this.hasAttribute('required') && !this.value.trim()) {
                this.classList.add('is-invalid');
            } else {
                this.classList.remove('is-invalid');
            }
        });
        
        field.addEventListener('input', function() {
            if (this.value.trim()) {
                this.classList.remove('is-invalid');
            }
        });
    });
    
    // Prepare JSON fields
    document.querySelectorAll('.json-settings').forEach(field => {
        field.addEventListener('blur', function() {
            if (this.value.trim()) {
                try {
                    // Try to parse and format the JSON
                    const jsonObj = JSON.parse(this.value);
                    this.value = JSON.stringify(jsonObj, null, 2);
                    this.classList.remove('is-invalid');
                } catch (e) {
                    this.classList.add('is-invalid');
                    console.error('Invalid JSON:', e);
                }
            }
        });
    });
    
    // Initial setup
    attachQuestionEventHandlers();
    
    // If no questions exist, add one by default
    if (formCount === 0) {
        addQuestionBtn.click();
    }
});