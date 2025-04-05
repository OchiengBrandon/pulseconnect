import pandas as pd
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, Paragraph, Spacer

# Analytics Functions
def analyze_choice_question(content, q_df, question, styles, brand_colors):
    """
    Analyze and add visualizations for choice-based questions
    """
    
    
    if 'response' in q_df.columns and not q_df['response'].empty:
        response_counts = q_df['response'].value_counts()
        
        # Create a table for the response distribution
        data = [['Response', 'Count', 'Percentage']]
        total_responses = len(q_df)
        
        for response, count in response_counts.items():
            percentage = (count / total_responses) * 100
            data.append([str(response), int(count), f"{percentage:.1f}%"])
        
        # Add summary table
        table = Table(data, colWidths=[250, 60, 80])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), brand_colors['primary']),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), brand_colors['background']),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        content.append(table)
        
        # Add visualization using reportlab
        if len(response_counts) > 0:
            try:
                # For few options (<=5), use pie chart
                if len(response_counts) <= 5:
                    drawing = Drawing(400, 200)
                    pie = Pie()
                    pie.x = 150
                    pie.y = 50
                    pie.width = 150
                    pie.height = 150
                    pie.data = response_counts.values.tolist()
                    pie.labels = [str(label) for label in response_counts.index.tolist()]
                    
                    # Set custom slice colors
                    color_list = [
                        brand_colors['primary'], 
                        brand_colors['secondary'],
                        brand_colors['tertiary'],
                        brand_colors['quaternary'],
                        brand_colors['quinary']
                    ]
                    for i, _ in enumerate(pie.data):
                        if i < len(color_list):
                            pie.slices[i].fillColor = color_list[i]
                    
                    pie.slices.strokeWidth = 0.5
                    pie.sideLabels = True
                    
                    # Create legend
                    legend = Legend()
                    legend.alignment = 'right'
                    legend.x = 330
                    legend.y = 150
                    legend.colorNamePairs = [(color_list[i % len(color_list)], 
                                           str(label)) for i, label in 
                                          enumerate(response_counts.index.tolist())]
                    
                    drawing.add(pie)
                    drawing.add(legend)
                    content.append(drawing)
                else:
                    # For many options, use horizontal bar chart
                    drawing = Drawing(500, 250)
                    bc = VerticalBarChart()
                    bc.x = 50
                    bc.y = 50
                    bc.height = 150
                    bc.width = 350
                    
                    # Sort by count for better visualization
                    sorted_counts = response_counts.sort_values(ascending=False)
                    bc.data = [sorted_counts.values.tolist()]
                    
                    # Truncate long labels
                    cat_names = []
                    for name in sorted_counts.index.tolist():
                        if len(str(name)) > 20:
                            cat_names.append(str(name)[:17] + "...")
                        else:
                            cat_names.append(str(name))
                    
                    bc.categoryAxis.categoryNames = cat_names
                    bc.categoryAxis.labels.angle = 30
                    bc.categoryAxis.labels.boxAnchor = 'ne'
                    bc.categoryAxis.labels.dx = -8
                    bc.categoryAxis.labels.dy = -2
                    
                    bc.valueAxis.valueMin = 0
                    bc.valueAxis.valueMax = max(sorted_counts.values) * 1.1
                    bc.valueAxis.valueStep = max(1, int(max(sorted_counts.values) / 5))
                    
                    bc.bars[0].fillColor = brand_colors['primary']
                    drawing.add(bc)
                    content.append(drawing)
                
                # Add insights
                add_choice_question_insights(content, response_counts, total_responses, styles)
                
            except Exception as e:
                content.append(Paragraph(f"Could not generate visualization: {str(e)}", styles['Normal']))
    else:
        content.append(Paragraph("No response data available for this question.", styles['Normal']))


def analyze_scale_question(content, q_df, question, styles, brand_colors):
    """
    Analyze and add visualizations for scale-based questions
    """
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.platypus import Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    
    if 'response' in q_df.columns and q_df['response'].notna().any():
        # Try to convert responses to numeric
        try:
            q_df['response_numeric'] = pd.to_numeric(q_df['response'])
            
            # Calculate statistics
            avg_rating = q_df['response_numeric'].mean()
            median_rating = q_df['response_numeric'].median()
            std_dev = q_df['response_numeric'].std()
            min_rating = q_df['response_numeric'].min()
            max_rating = q_df['response_numeric'].max()
            q1 = q_df['response_numeric'].quantile(0.25)
            q3 = q_df['response_numeric'].quantile(0.75)
            
            # Create statistics table
            stats_data = [
                ['Metric', 'Value', 'Description'],
                ['Average Rating', f"{avg_rating:.2f}", 'Mean of all responses'],
                ['Median Rating', f"{median_rating:.2f}", 'Middle value of sorted responses'],
                ['Standard Deviation', f"{std_dev:.2f}", 'Measure of response variation'],
                ['Minimum', f"{min_rating:.2f}", 'Lowest rating given'],
                ['Maximum', f"{max_rating:.2f}", 'Highest rating given'],
                ['Q1 (25th Percentile)', f"{q1:.2f}", '25% of responses are below this value'],
                ['Q3 (75th Percentile)', f"{q3:.2f}", '75% of responses are below this value'],
                ['Response Count', len(q_df), 'Total number of responses']
            ]
            
            stats_table = Table(stats_data, colWidths=[150, 70, 200])
            stats_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), brand_colors['primary']),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BACKGROUND', (0, 1), (-1, -1), brand_colors['background']),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            content.append(stats_table)
            content.append(Spacer(1, 10))
            
            # Add distribution information
            rating_counts = q_df['response_numeric'].value_counts().sort_index()
            
            # Create bar chart for distribution
            try:
                drawing = Drawing(400, 200)
                bc = VerticalBarChart()
                bc.x = 50
                bc.y = 50
                bc.height = 125
                bc.width = 300
                bc.data = [rating_counts.values.tolist()]
                bc.categoryAxis.categoryNames = [str(x) for x in rating_counts.index.tolist()]
                bc.valueAxis.valueMin = 0
                bc.valueAxis.valueMax = max(rating_counts.values) * 1.1
                bc.valueAxis.valueStep = max(1, int(max(rating_counts.values) / 5))
                bc.bars[0].fillColor = brand_colors['primary']
                
                # Add labels and title
                bc.categoryAxis.labels.fontName = 'Helvetica'
                bc.valueAxis.labels.fontName = 'Helvetica'
                bc.categoryAxis.title = "Rating"
                bc.valueAxis.title = "Number of Responses"
                
                drawing.add(bc)
                content.append(drawing)
                
                # Add insights based on distribution
                add_scale_question_insights(content, q_df['response_numeric'], styles)
                
            except Exception as e:
                content.append(Paragraph(f"Could not generate bar chart: {str(e)}", styles['Normal']))
        
        except Exception as e:
            content.append(Paragraph(f"Could not convert scale responses to numeric values: {str(e)}", styles['Normal']))
    else:
        content.append(Paragraph("No response data available for this question.", styles['Normal']))


def analyze_text_question(content, q_df, question, styles, brand_colors):
    """
    Analyze and add visualizations for text-based questions
    """
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, ListFlowable, ListItem
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.lib import colors
    from collections import Counter
    import re
    
    if 'response' in q_df.columns:
        text_responses = q_df['response'].dropna().tolist()
        
        # Calculate text statistics
        if text_responses:
            try:
                word_counts = [len(str(resp).split()) for resp in text_responses]
                avg_words = sum(word_counts) / len(word_counts) if word_counts else 0
                max_words = max(word_counts) if word_counts else 0
                min_words = min(word_counts) if word_counts else 0
                
                # Calculate character statistics
                char_counts = [len(str(resp)) for resp in text_responses]
                avg_chars = sum(char_counts) / len(char_counts) if char_counts else 0
                
                # Create text statistics table
                stats_data = [
                    ['Metric', 'Value'],
                    ['Number of responses', len(text_responses)],
                    ['Average response length', f"{avg_words:.1f} words ({avg_chars:.1f} characters)"],
                    ['Longest response', f"{max_words} words"],
                    ['Shortest response', f"{min_words} words"]
                ]
                
                stats_table = Table(stats_data, colWidths=[200, 200])
                stats_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), brand_colors['primary']),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('BACKGROUND', (0, 1), (-1, -1), brand_colors['background']),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                content.append(stats_table)
                content.append(Spacer(1, 10))
                
                # Perform word frequency analysis
                content.append(Paragraph("Word Frequency Analysis:", styles['NormalBold']))
                
                # Combine all text and extract word frequency
                all_text = ' '.join([str(resp) for resp in text_responses])
                words = re.findall(r'\b[a-zA-Z]{3,}\b', all_text.lower())  # Only words with 3+ chars
                
                # Remove common stop words
                stop_words = ['the', 'and', 'for', 'with', 'was', 'that', 'this', 'are', 'not', 'from']
                filtered_words = [word for word in words if word not in stop_words]
                
                # Get most common words
                word_freq = Counter(filtered_words).most_common(10)
                
                if word_freq:
                    # Create word frequency table and chart
                    freq_data = [['Word', 'Frequency']]
                    freq_data.extend(word_freq)
                    
                    freq_table = Table(freq_data, colWidths=[150, 70])
                    freq_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), brand_colors['secondary']),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black)
                    ]))
                    content.append(freq_table)
                    content.append(Spacer(1, 10))
                    
                    # Create word frequency chart
                    try:
                        drawing = Drawing(400, 200)
                        bc = VerticalBarChart()
                        bc.x = 50
                        bc.y = 50
                        bc.height = 125
                        bc.width = 300
                        
                        # Sort by frequency for better visualization
                        bc.data = [[freq for _, freq in word_freq]]
                        bc.categoryAxis.categoryNames = [word for word, _ in word_freq]
                        bc.valueAxis.valueMin = 0
                        bc.valueAxis.valueMax = max([freq for _, freq in word_freq]) * 1.1
                        bc.valueAxis.valueStep = max(1, int(max([freq for _, freq in word_freq]) / 5))
                        bc.bars[0].fillColor = brand_colors['secondary']
                        
                        # Add labels and title
                        bc.categoryAxis.labels.fontName = 'Helvetica'
                        bc.categoryAxis.labels.angle = 45
                        bc.categoryAxis.labels.boxAnchor = 'ne'
                        bc.valueAxis.labels.fontName = 'Helvetica'
                        
                        drawing.add(bc)
                        content.append(drawing)
                    except Exception as e:
                        content.append(Paragraph(f"Could not generate word frequency chart: {str(e)}", styles['Normal']))
                
                # Add theme and sentiment analysis
                content.append(Spacer(1, 10))
                content.append(Paragraph("Key Themes:", styles['NormalBold']))
                
                # Extract themes (Here we're simplifying by using most common word pairs)
                bigrams = extract_bigrams(text_responses)
                
                theme_items = []
                for theme, count in bigrams[:5]:
                    theme_items.append(ListItem(Paragraph(f"{theme} (mentioned in {count} responses)", styles['Normal'])))
                
                if theme_items:
                    content.append(ListFlowable(theme_items, bulletType='bullet'))
                else:
                    content.append(Paragraph("No clear themes identified.", styles['Normal']))
                
                # Show sample responses with analysis
                content.append(Spacer(1, 10))
                content.append(Paragraph("Sample Responses with Analysis:", styles['NormalBold']))
                
                # Get up to 3 representative responses (choose longest ones as they're typically more informative)
                sample_responses = sorted(text_responses, key=len, reverse=True)[:3]
                
                for i, resp in enumerate(sample_responses):
                    content.append(Paragraph(f"<b>Response {i+1}:</b> {str(resp)}", styles['Normal']))
                    
                    # Add simple sentiment and length analysis
                    word_count = len(str(resp).split())
                    sentiment = simple_sentiment_analysis(str(resp))
                    
                    content.append(Paragraph(
                        f"<i>Analysis: {word_count} words. Sentiment appears to be {sentiment}.</i>", 
                        styles['InsightText']
                    ))
                    content.append(Spacer(1, 5))
                
            except Exception as e:
                content.append(Paragraph(f"Error analyzing text responses: {str(e)}", styles['Normal']))
        else:
            content.append(Paragraph("No text responses available for analysis.", styles['Normal']))
    else:
        content.append(Paragraph("No response column found in the data.", styles['Normal']))
    
    return content


def extract_bigrams(responses):
    """
    Extract most common word pairs (bigrams) from text responses
    """
    from collections import Counter
    import re
    
    # Combine all responses
    all_text = ' '.join([str(resp) for resp in responses])
    
    # Clean text
    clean_text = re.sub(r'[^\w\s]', '', all_text.lower())
    words = clean_text.split()
    
    # Filter out stop words
    stop_words = ['the', 'and', 'for', 'with', 'was', 'that', 'this', 'are', 'not', 'from',
                 'a', 'to', 'in', 'of', 'is', 'it', 'on', 'at', 'by', 'an', 'as', 'be']
    filtered_words = [word for word in words if word not in stop_words and len(word) > 2]
    
    # Generate bigrams
    bigrams = []
    for i in range(len(filtered_words) - 1):
        bigrams.append(f"{filtered_words[i]} {filtered_words[i+1]}")
    
    # Count and return most common
    bigram_counts = Counter(bigrams)
    
    # Convert counts to response occurrences (approximate)
    response_counts = []
    total_responses = len(responses)
    
    for bigram, count in bigram_counts.most_common(10):
        # Estimate in how many responses this bigram appears
        est_responses = min(total_responses, max(1, int(count / 3)))
        response_counts.append((bigram, est_responses))
    
    return response_counts


def simple_sentiment_analysis(text):
    """
    Perform a simple sentiment analysis on text
    """
    # Define simple sentiment word lists
    positive_words = [
        'good', 'great', 'excellent', 'amazing', 'wonderful', 'fantastic', 'happy',
        'best', 'better', 'love', 'like', 'enjoy', 'helpful', 'positive', 'awesome',
        'easy', 'perfect', 'satisfied', 'recommend', 'quality'
    ]
    
    negative_words = [
        'bad', 'poor', 'terrible', 'awful', 'horrible', 'worst', 'worse', 'hate',
        'dislike', 'difficult', 'hard', 'disappointing', 'negative', 'problem',
        'issue', 'broken', 'complicated', 'confused', 'unhappy', 'dissatisfied'
    ]
    
    # Count occurrences
    text_lower = text.lower()
    pos_count = sum(1 for word in positive_words if f' {word} ' in f' {text_lower} ')
    neg_count = sum(1 for word in negative_words if f' {word} ' in f' {text_lower} ')
    
    # Determine sentiment
    if pos_count > neg_count * 2:
        return "very positive"
    elif pos_count > neg_count:
        return "somewhat positive"
    elif neg_count > pos_count * 2:
        return "very negative"
    elif neg_count > pos_count:
        return "somewhat negative"
    else:
        return "neutral"


def calculate_completion_rate(df):
    """
    Calculate the overall completion rate for the dataset
    
    Args:
        df: DataFrame containing the dataset records
    
    Returns:
        float: Completion rate as a percentage
    """
    # Count unique users
    total_users = df['user_id'].nunique()
    
    if total_users == 0:
        return 0.0
    
    # Count unique questions
    total_questions = df['question_id'].nunique()
    
    # Calculate questions per user
    questions_per_user = df.groupby('user_id')['question_id'].nunique().mean()
    
    # Calculate completion rate
    completion_rate = (questions_per_user / total_questions) * 100 if total_questions > 0 else 0
    
    return completion_rate

def calculate_average_time_spent(df):
    """
    Calculate the average time users spent on the poll
    
    Args:
        df: DataFrame containing the dataset records
    
    Returns:
        str: Formatted average time spent
    """
    import pandas as pd
    
    # Check if timestamp column exists and has data
    if 'timestamp' not in df.columns or df['timestamp'].isna().all():
        return "N/A"
    
    try:
        # Convert timestamps to datetime objects
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Group by user_id and calculate time difference between first and last response
        user_times = df.groupby('user_id')['timestamp'].agg(['min', 'max'])
        user_times['duration'] = (user_times['max'] - user_times['min']).dt.total_seconds() / 60  # in minutes
        
        # Calculate average duration
        avg_minutes = user_times['duration'].mean()
        
        # Format the result
        if avg_minutes < 1:
            return f"{avg_minutes * 60:.1f} seconds"
        elif avg_minutes < 60:
            return f"{avg_minutes:.1f} minutes"
        else:
            hours = int(avg_minutes // 60)
            minutes = int(avg_minutes % 60)
            return f"{hours} hour{'s' if hours != 1 else ''} {minutes} minute{'s' if minutes != 1 else ''}"
    
    except Exception:
        return "N/A"

def generate_key_insights(df, poll_data):
    """
    Generate key insights from the overall dataset
    
    Args:
        df: DataFrame containing the dataset records
        poll_data: List of poll dictionaries
    
    Returns:
        list: List of insight strings
    """
    insights = []
    
    # Check if we have data to analyze
    if df.empty:
        return ["No data available for analysis."]
    
    # Get overall response count
    total_responses = df['user_id'].nunique()
    insights.append(f"The dataset contains responses from {total_responses} participants across {len(poll_data)} polls.")
    
    # Identify most and least responded-to questions
    question_response_counts = df.groupby(['question_text'])['user_id'].nunique().sort_values(ascending=False)
    
    if not question_response_counts.empty:
        most_responded = question_response_counts.index[0]
        most_responded_count = question_response_counts.iloc[0]
        insights.append(f"The question with highest engagement was '{most_responded}' with {most_responded_count} responses.")
        
        # Only add least responded if we have more than one question
        if len(question_response_counts) > 1:
            least_responded = question_response_counts.index[-1]
            least_responded_count = question_response_counts.iloc[-1]
            insights.append(f"The question with lowest engagement was '{least_responded}' with {least_responded_count} responses.")
    
    # Identify trends in rating questions if applicable
    rating_questions = df[df['question_type'].isin(['rating_scale', 'likert_scale'])]
    if not rating_questions.empty:
        try:
            # Convert to numeric for analysis
            rating_questions['response_numeric'] = pd.to_numeric(rating_questions['response'], errors='coerce')
            
            # Group by question and calculate average rating
            avg_ratings = rating_questions.groupby('question_text')['response_numeric'].mean().sort_values(ascending=False)
            
            if not avg_ratings.empty:
                highest_rated = avg_ratings.index[0]
                highest_rating = avg_ratings.iloc[0]
                insights.append(f"The highest rated item was '{highest_rated}' with an average score of {highest_rating:.2f}.")
                
                if len(avg_ratings) > 1:
                    lowest_rated = avg_ratings.index[-1]
                    lowest_rating = avg_ratings.iloc[-1]
                    insights.append(f"The lowest rated item was '{lowest_rated}' with an average score of {lowest_rating:.2f}.")
        except:
            # Skip this analysis if conversion to numeric fails
            pass
    
    # Add completion time insight if available
    if 'timestamp' in df.columns and not df['timestamp'].isna().all():
        avg_time = calculate_average_time_spent(df)
        if avg_time != "N/A":
            insights.append(f"Participants spent an average of {avg_time} completing the polls.")
    
    return insights

def generate_poll_insights(poll_df, poll):
    """
    Generate insights specific to a single poll
    
    Args:
        poll_df: DataFrame filtered for a specific poll
        poll: Dictionary containing poll data
    
    Returns:
        list: List of insight strings
    """
    insights = []
    
    # Check if we have data to analyze
    if poll_df.empty:
        return ["No data available for this poll."]
    
    # Get response count for this poll
    poll_responses = poll_df['user_id'].nunique()
    
    # Check if this poll has multiple questions
    question_count = len(poll.get('questions', []))
    if question_count > 1:
        # Calculate average responses per question
        avg_responses_per_question = poll_df.groupby('question_id')['user_id'].nunique().mean()
        
        # Calculate drop-off rate
        first_question_responses = poll_df[poll_df['question_id'] == poll.get('questions', [{}])[0].get('question_id')]['user_id'].nunique()
        last_question_responses = poll_df[poll_df['question_id'] == poll.get('questions', [{}])[-1].get('question_id')]['user_id'].nunique()
        
        if first_question_responses > 0:
            drop_off_rate = ((first_question_responses - last_question_responses) / first_question_responses) * 100
            insights.append(f"Poll completion drop-off rate: {drop_off_rate:.1f}% (started: {first_question_responses}, completed: {last_question_responses})")
    
    # Find most common responses for single/multiple choice questions
    choice_questions = poll_df[poll_df['question_type'].isin(['single_choice', 'multiple_choice'])]
    if not choice_questions.empty:
        # Group by question and find most common response
        common_responses = choice_questions.groupby('question_text')['response'].agg(
            lambda x: x.value_counts().index[0] if len(x.value_counts()) > 0 else None
        )
        
        # Add insights for up to 2 questions
        for i, (question, response) in enumerate(common_responses.items()):
            if i >= 2:  # Limit to 2 questions to avoid overwhelming
                break
            if response:
                insights.append(f"For '{question}', the most common response was '{response}'.")
    
    # Analyze rating questions
    rating_questions = poll_df[poll_df['question_type'].isin(['rating_scale', 'likert_scale'])]
    if not rating_questions.empty:
        try:
            # Convert to numeric for analysis
            rating_questions['response_numeric'] = pd.to_numeric(rating_questions['response'], errors='coerce')
            
            # Find highest and lowest rated items
            avg_ratings = rating_questions.groupby('question_text')['response_numeric'].mean().sort_values(ascending=False)
            
            if len(avg_ratings) > 0:
                highest_question = avg_ratings.index[0]
                highest_rating = avg_ratings.iloc[0]
                insights.append(f"Highest rated item: '{highest_question}' ({highest_rating:.2f}/5)")
                
                if len(avg_ratings) > 1:
                    lowest_question = avg_ratings.index[-1]
                    lowest_rating = avg_ratings.iloc[-1]
                    insights.append(f"Lowest rated item: '{lowest_question}' ({lowest_rating:.2f}/5)")
        except:
            pass
    
    return insights

def add_choice_question_insights(content, response_counts, total_responses, styles):
    """
    Add insights for choice questions
    
    Args:
        content: List to append content to
        response_counts: Series containing response counts
        total_responses: Total number of responses
        styles: ReportLab style sheet
    """
    from reportlab.platypus import Paragraph, Spacer
    
    # Calculate percentages
    percentages = (response_counts / total_responses * 100).sort_values(ascending=False)
    
    # Generate insights based on distribution
    insights = []
    
    # Most common response
    if not percentages.empty:
        top_response = percentages.index[0]
        top_percentage = percentages.iloc[0]
        insights.append(f"The most common response was '{top_response}' selected by {top_percentage:.1f}% of respondents.")
        
        # Check for strong consensus (>70%)
        if top_percentage > 70:
            insights.append(f"There is a strong consensus around the '{top_response}' option.")
        
        # Check for close top choices
        if len(percentages) > 1 and (top_percentage - percentages.iloc[1]) < 10:
            second_response = percentages.index[1]
            second_percentage = percentages.iloc[1]
            insights.append(f"'{top_response}' ({top_percentage:.1f}%) and '{second_response}' ({second_percentage:.1f}%) received similar levels of support.")
        
        # Check for polarized responses (bimodal distribution)
        if len(percentages) > 2 and percentages.iloc[0] > 30 and percentages.iloc[1] > 30 and (percentages.iloc[1] - percentages.iloc[2]) > 20:
            insights.append("Responses show a polarized opinion with two dominant choices.")
    
    # Add insights to content
    if insights:
        content.append(Spacer(1, 10))
        content.append(Paragraph("Analysis:", styles['NormalBold']))
        for insight in insights:
            content.append(Paragraph(f"• {insight}", styles['InsightText']))

def add_scale_question_insights(content, response_numeric, styles):
    """
    Add insights for scale questions
    
    Args:
        content: List to append content to
        response_numeric: Series containing numeric responses
        styles: ReportLab style sheet
    """
    from reportlab.platypus import Paragraph, Spacer
    
    # Generate insights based on distribution
    insights = []
    
    # Basic statistics
    mean = response_numeric.mean()
    median = response_numeric.median()
    std_dev = response_numeric.std()
    
    # Interpret mean score
    if mean > 4:
        insights.append(f"Very positive rating with an average of {mean:.2f} out of 5.")
    elif mean > 3:
        insights.append(f"Generally positive rating with an average of {mean:.2f} out of 5.")
    elif mean > 2:
        insights.append(f"Neutral to slightly positive rating with an average of {mean:.2f} out of 5.")
    else:
        insights.append(f"Below average rating with a score of {mean:.2f} out of 5.")
    
    # Check for consensus vs. divergence
    if std_dev < 0.8:
        insights.append(f"Responses show strong consensus (standard deviation: {std_dev:.2f}).")
    elif std_dev > 1.5:
        insights.append(f"Responses show significant variability (standard deviation: {std_dev:.2f}), indicating divergent opinions.")
    
    # Check for skewness (difference between mean and median)
    if abs(mean - median) > 0.3:
        if mean > median:
            insights.append("The distribution is positively skewed with a few high ratings pulling up the average.")
        else:
            insights.append("The distribution is negatively skewed with a few low ratings pulling down the average.")
    
    # Add insights to content
    if insights:
        content.append(Spacer(1, 10))
        content.append(Paragraph("Analysis:", styles['NormalBold']))
        for insight in insights:
            content.append(Paragraph(f"• {insight}", styles['InsightText']))

def extract_bigrams(text_responses):
    """
    Extract common bigrams (word pairs) from text responses
    
    Args:
        text_responses: List of text responses
    
    Returns:
        list: List of (bigram, count) tuples
    """
    from collections import Counter
    import re
    
    # Combine all responses
    all_text = ' '.join([str(resp).lower() for resp in text_responses])
    
    # Clean text and split into words
    words = re.findall(r'\b[a-zA-Z]{3,}\b', all_text)
    
    # Skip if not enough words
    if len(words) < 2:
        return []
    
    # Create bigrams
    bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words)-1)]
    
    # Count and return top bigrams with a count
    bigram_counts = Counter(bigrams).most_common(5)
    
    # Add a count indicator to each bigram
    return [(bigram, count) for bigram, count in bigram_counts]

def simple_sentiment_analysis(text):
    """
    Perform very simple sentiment analysis on text
    
    Args:
        text: Text to analyze
    
    Returns:
        str: Sentiment description
    """
    # Lists of positive and negative words
    positive_words = [
        'good', 'great', 'excellent', 'wonderful', 'amazing', 'fantastic', 'terrific', 
        'outstanding', 'exceptional', 'impressive', 'remarkable', 'like', 'love', 'best',
        'happy', 'pleased', 'satisfied', 'enjoy', 'positive', 'recommend', 'helpful',
        'useful', 'beneficial', 'valuable', 'favorable'
    ]
    
    negative_words = [
        'bad', 'poor', 'terrible', 'horrible', 'awful', 'disappointing', 'dreadful',
        'dislike', 'hate', 'worst', 'unhappy', 'frustrated', 'dissatisfied', 'negative',
        'useless', 'waste', 'problem', 'difficult', 'hard', 'complicated', 'confusing',
        'expensive', 'overpriced', 'unreliable'
    ]
    
    # Normalize text
    text_lower = text.lower()
    
    # Count occurrences
    pos_count = sum(1 for word in positive_words if word in text_lower)
    neg_count = sum(1 for word in negative_words if word in text_lower)
    
    # Determine sentiment
    if pos_count > neg_count * 2:
        return "strongly positive"
    elif pos_count > neg_count:
        return "somewhat positive"
    elif neg_count > pos_count * 2:
        return "strongly negative"
    elif neg_count > pos_count:
        return "somewhat negative"
    else:
        return "neutral or mixed"